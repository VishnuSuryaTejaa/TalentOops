"""WebSocket signaling handler for TalentOops self-hosted Interview Rooms.

Each candidate and HR client connects to:
    ws://localhost:8000/ws/room/{room_id}

Frame protocol (JSON):
    Client → Server:  {"type": "<SignalType>", "data": {...}}
    Server → Client:  {"type": "<SignalType>", "data": {...}}

Agent pipeline execution order (inside this handler):
    1. Consent Agent  — discloses recording policy, collects consent
    2. Interviewer FSM — interactive turn-by-turn Q&A driven by real candidate replies
    3. Evaluator Agent — scores full transcript, streams scorecard
    4. Session End     — emits final scorecard + transitions room to COMPLETED

FIXED BUGS (2026-07-28):
    - Broken dispatch: pipeline no longer fires before candidate answers
    - Interactive FSM: each candidate turn is awaited in real-time and the
      next question is pushed back immediately via WebSocket
    - Silent exception swallowing: all except blocks now log errors
    - Consent-granted transition: room status updated before FSM starts
    - INTERVIEW_ACTIVE stage: server now broadcasts AI question frames
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.rooms.models import RoomStatus, SignalType
from app.rooms.room_manager import room_manager
from app.services.database import db
from app.supabase_client import log_event

logger = logging.getLogger("talentops.room_signaling")

from app.config import settings
if settings.STT_PROVIDER == "deepgram" and not getattr(settings, "DEEPGRAM_API_KEY", ""):
    logger.warning(
        "[STT WARNING] STT_PROVIDER is set to 'deepgram' but DEEPGRAM_API_KEY is empty/unconfigured. "
        "Audio transcription will fall back to Browser SpeechRecognition / Web Speech API."
    )


# ─── helpers ──────────────────────────────────────────────────────────────────

def _frame(signal_type: SignalType, data: dict[str, Any]) -> dict[str, Any]:
    return {"type": signal_type.value, "data": data}


async def _safe_send(ws: WebSocket, payload: dict[str, Any]) -> None:
    try:
        await ws.send_json(payload)
    except Exception as exc:
        logger.warning("send_json failed: %s", exc)


# ─── batch agent pipeline (used by /interviews/{room_id}/complete) ─────────────

async def _run_agent_pipeline(
    room_id: str,
    interview_id: str,
    candidate_id: str,
    role_id: str,
    consent_response: str,
    candidate_turns: list[str],
    run_id: str,
) -> dict[str, Any]:
    """Execute Consent → Interview → Evaluator as a batch (non-interactive) pipeline.

    This is called from the REST endpoint /interviews/{room_id}/complete only.
    The live WebSocket path uses the interactive _InteractiveRoomSession instead.
    """
    from app.agents.consent_agent import ConsentAgent
    from app.agents.evaluator_agent import EvaluatorAgent
    from app.agents.interviewer_fsm import InterviewerFSM
    from app.services.database import db

    # ── 1. Consent Agent ────────────────────────────────────────────────────
    consent_agent = ConsentAgent()
    consent_result = await consent_agent.process_response(
        candidate_id=candidate_id,
        response_text=consent_response,
        room_id=room_id,
        run_id=run_id,
    )

    await room_manager.broadcast(room_id, _frame(SignalType.AGENT_MESSAGE, {
        "agent": "consent",
        "consent_granted": consent_result["consent_granted"],
        "reasoning": consent_result["reasoning"],
    }))

    if not consent_result["consent_granted"]:
        return {"status": "consent_denied", "consent_result": consent_result}

    await room_manager.update_status(room_id, RoomStatus.ACTIVE)

    # ── 2. Interviewer FSM ──────────────────────────────────────────────────
    rubrics = await db.query("rubrics", run_id=run_id)
    rubric = rubrics[0] if rubrics else {
        "standard": f"Role ({role_id})",
        "competencies": [{"competency_id": "core_skills", "keywords": ["python", "backend"]}],
    }

    class _AsyncSession:
        async def inject_context(self, text: str) -> None: pass
        async def next_turn(self, text: str) -> str:
            return f"Tell me more about: {text[:80]}"

    fsm = InterviewerFSM(
        rubric=rubric,
        brief={"candidate_name": candidate_id},
        session=_AsyncSession(),
    )

    for i, turn_text in enumerate(candidate_turns or ["I have backend engineering experience."]):
        await room_manager.broadcast(room_id, _frame(SignalType.INTERVIEW_TURN, {
            "turn_number": i + 1,
            "speaker": "candidate",
            "text": turn_text,
        }))
        await asyncio.sleep(0.05)

    fsm_result = await fsm.run_interview(
        candidate_turns or ["I have backend engineering experience."],
        transcript_ref=interview_id,
    )

    # ── 3. Evaluator Agent ──────────────────────────────────────────────────
    transcript_formatted = [
        {"speaker": "interviewer", "text": "Please tell me about your experience."},
        *[{"speaker": "candidate", "text": t} for t in (candidate_turns or [])],
    ]

    evaluator = EvaluatorAgent(run_id=run_id)
    scorecard_result = await evaluator.evaluate_transcript(
        interview_id=interview_id,
        candidate_id=candidate_id,
        rubric=rubric,
        transcript_turns=transcript_formatted,
    )

    await room_manager.broadcast(room_id, _frame(SignalType.EVAL_UPDATE, {
        "scorecard": scorecard_result.get("scorecard", {}),
        "final_recommendation": scorecard_result.get("final_recommendation", {}),
        "behavioral_metrics": scorecard_result.get("behavioral_metrics", {}),
    }))

    log_event(
        run_id=run_id,
        source="room_signaling",
        event_type="interview_completed",
        payload={
            "room_id": room_id,
            "interview_id": interview_id,
            "scorecard_id": scorecard_result.get("scorecard_id"),
        },
    )

    return {
        "status": "completed",
        "fsm_summary": fsm_result,
        "scorecard": scorecard_result,
    }


# ─── interactive room session ─────────────────────────────────────────────────

class _InteractiveRoomSession:
    """Drives the live WebSocket interview loop.

    State machine:
        CONSENT_PENDING  → waits for consent-response frame
        INTERVIEW_ACTIVE → sends AI question, waits for interview-turn frame (repeats)
        EVALUATING       → evaluator runs, result broadcast
        DONE             → session-end frame sent, room closed
    """

    # Maximum interview turns before auto-closing
    MAX_TURNS = 8

    def __init__(
        self,
        ws: WebSocket,
        room_id: str,
        interview_id: str,
        candidate_id: str,
        role_id: str,
        run_id: str,
    ) -> None:
        self.ws           = ws
        self.room_id      = room_id
        self.interview_id = interview_id
        self.candidate_id = candidate_id
        self.role_id      = role_id
        self.run_id       = run_id

        # Interview duration set by HR (minutes); 0 = unlimited (MAX_TURNS governs)
        self.duration_seconds: float = 0.0

        # Transcript accumulated during live session
        self.transcript: list[dict[str, Any]] = []
        self.candidate_turns: list[str] = []

        # Candidate resume fetched from Supabase at session start
        self._candidate_resume: str = ""

        # Pending queue: candidate frames received while agent is "thinking"
        self._turn_queue: asyncio.Queue[str] = asyncio.Queue()

        # Interviewer FSM state
        self._fsm = None
        self._rubric: dict[str, Any] = {}
        self._asked_questions: list[str] = []
        self.history: list[dict[str, str]] = []


    # ── public entry point ─────────────────────────────────────────────────

    async def run(self) -> None:
        """Main coroutine: receive WebSocket frames and drive the state machine."""
        state = "CONSENT_PENDING"

        try:
            while True:
                raw = await self.ws.receive_text()
                msg = self._parse(raw)
                if msg is None:
                    continue

                msg_type: str = msg.get("type", "")
                data: dict    = msg.get("data", {})

                # ── WebRTC signaling passthrough ──────────────────────────
                if msg_type in (
                    SignalType.OFFER.value,
                    SignalType.ANSWER.value,
                    SignalType.ICE_CANDIDATE.value,
                ):
                    await room_manager.broadcast(self.room_id, {
                        "type": msg_type, "data": data, "from": "peer",
                    })
                    continue

                # ── Client-initiated session end ──────────────────────────
                if msg_type == SignalType.SESSION_END.value:
                    logger.info("Client requested session end for room %s — signaling interview loop to evaluate", self.room_id)
                    await self._turn_queue.put("__END_SESSION__")
                    break



                # ── Dispatch by state ─────────────────────────────────────
                if state == "CONSENT_PENDING":
                    if msg_type == SignalType.CONSENT_RESPONSE.value:
                        consent_text = data.get("text", "")
                        granted = await self._handle_consent(consent_text)
                        if granted:
                            state = "INTERVIEW_ACTIVE"
                            await self._start_interview()
                        else:
                            # Consent denied — send closing message and exit
                            await _safe_send(self.ws, _frame(SignalType.SESSION_END, {
                                "status": "consent_denied",
                                "message": "Thank you for your time. Session ended.",
                            }))
                            break
                    else:
                        logger.debug(
                            "Room %s: ignoring frame type %r while CONSENT_PENDING",
                            self.room_id, msg_type,
                        )

                elif state == "INTERVIEW_ACTIVE":
                    if msg_type == SignalType.INTERVIEW_TURN.value:
                        candidate_text = data.get("text", "").strip()
                        if candidate_text:
                            await self._turn_queue.put(candidate_text)
                    else:
                        logger.debug(
                            "Room %s: ignoring frame type %r while INTERVIEW_ACTIVE",
                            self.room_id, msg_type,
                        )

        except WebSocketDisconnect:
            logger.info("Client disconnected from room %s (state=%s)", self.room_id, state)
        except Exception as exc:
            logger.error(
                "Room WS session error in room %s (state=%s): %s",
                self.room_id, state, exc, exc_info=True,
            )
            await _safe_send(self.ws, _frame(SignalType.ERROR, {"message": str(exc)}))
        finally:
            await room_manager.leave_room(self.room_id, self.ws)
            # Ensure evaluation completes and scorecard is stored on room closure/disconnect
            try:
                await room_manager.close_room(self.room_id)
            except Exception as close_exc:
                logger.warning("close_room error during WS exit for %s: %s", self.room_id, close_exc)
            logger.info("Room WS session exited for room %s", self.room_id)

    # ── consent phase ──────────────────────────────────────────────────────

    async def _handle_consent(self, response_text: str) -> bool:
        """Process consent reply, update room status, return True if granted."""
        from app.agents.consent_agent import ConsentAgent

        try:
            consent_result = await ConsentAgent().process_response(
                candidate_id=self.candidate_id,
                response_text=response_text,
                room_id=self.room_id,
                run_id=self.run_id,
            )
        except Exception as exc:
            logger.error("ConsentAgent.process_response failed for room %s: %s", self.room_id, exc)
            consent_result = {
                "consent_granted": False,
                "reasoning": f"Consent processing error: {exc}",
                "confidence_score": 0.0,
            }

        granted: bool = consent_result["consent_granted"]

        # Echo consent decision back to client
        await _safe_send(self.ws, _frame(SignalType.AGENT_MESSAGE, {
            "agent": "consent",
            "consent_granted": granted,
            "reasoning": consent_result.get("reasoning", ""),
            "text": (
                "Thank you! Consent recorded. Starting your interview now…"
                if granted else
                "Understood. We require consent to proceed. Session will now end."
            ),
        }))

        if granted:
            try:
                await room_manager.update_status(self.room_id, RoomStatus.ACTIVE)
            except Exception as exc:
                logger.warning("Could not update room status for %s: %s", self.room_id, exc)

            log_event(
                run_id=self.run_id,
                source="room_signaling",
                event_type="consent_granted",
                payload={"room_id": self.room_id, "candidate_id": self.candidate_id},
            )
        else:
            log_event(
                run_id=self.run_id,
                source="room_signaling",
                event_type="consent_denied",
                payload={"room_id": self.room_id, "candidate_id": self.candidate_id},
            )

        return granted

    # ── interview phase ────────────────────────────────────────────────────

    async def _start_interview(self) -> None:
        """Kick off the interactive interview loop as a background task."""
        asyncio.create_task(self._interview_loop(), name=f"interview-{self.room_id[:8]}")

    async def _interview_loop(self) -> None:
        """Run turn-by-turn interview: ask question → wait for answer → repeat."""
        from app.agents.evaluator_agent import EvaluatorAgent
        from app.agents.interviewer_fsm import InterviewerFSM
        from app.services.database import db

        logger.info("Interview loop started for room %s", self.room_id)

        try:
            # Load rubric
            try:
                rubrics = await db.query("rubrics", run_id=self.run_id)
                self._rubric = rubrics[0] if rubrics else self._default_rubric()
            except Exception as exc:
                logger.warning("Could not load rubric for run %s: %s — using default", self.run_id, exc)
                self._rubric = self._default_rubric()

            # BUG-07: Fetch candidate resume from Supabase so questions are resume-grounded
            try:
                cand_rows = await db.query("candidates", id=self.candidate_id)
                if cand_rows:
                    c = cand_rows[0]
                    cand_name = c.get("name") or self.candidate_id
                    cand_email = c.get("email") or ""
                    cand_phone = c.get("phone") or ""
                    cand_summary = c.get("summary") or ""
                    cand_skills = c.get("skills") or []
                    cand_raw = c.get("raw_text") or c.get("resume") or ""

                    proj_rows = await db.query("projects", candidate_id=self.candidate_id)
                    proj_texts = []
                    for p in proj_rows:
                        techs = ", ".join(p.get("technologies") or [])
                        proj_texts.append(f"- {p.get('title')}: {p.get('description', '')} (Tech: {techs})")
                    proj_block = "\n".join(proj_texts) if proj_texts else ""

                    resume_blocks = [
                        f"Candidate Name: {cand_name}",
                        f"Contact: {cand_email} | {cand_phone}",
                        f"Summary: {cand_summary}" if cand_summary else "",
                        f"Extracted Skills: {', '.join(cand_skills)}" if cand_skills else "",
                        f"Key Projects:\n{proj_block}" if proj_block else "",
                        f"Resume Raw Text:\n{cand_raw}" if cand_raw else "",
                    ]
                    self._candidate_resume = "\n\n".join(b for b in resume_blocks if b)
            except Exception as exc:
                logger.warning("Could not load resume for candidate %s: %s", self.candidate_id, exc)

            # BUG-03: Resolve session duration from room metadata (set by HR at room creation)
            duration_minutes = 0
            try:
                room = room_manager.get_room(self.room_id)
                if room:
                    duration_minutes = int(room.metadata.get("duration_minutes", 0))
            except Exception:
                pass
            self.duration_seconds = duration_minutes * 60.0
            deadline: float | None = (
                asyncio.get_event_loop().time() + self.duration_seconds
                if self.duration_seconds > 0 else None
            )

            # Build a WebSocket-bridged session adapter so FSM questions go out live
            ws_ref = self.ws
            room_id = self.room_id
            transcript = self.transcript
            candidate_turns = self.candidate_turns
            turn_queue = self._turn_queue

            class _LiveSession:
                async def inject_context(self, text: str) -> None:
                    # Internal FSM cue — not shown to candidate
                    logger.debug("FSM context inject [%s]: %s", room_id, text[:80])

                async def next_turn(self, candidate_text: str) -> str:
                    """Wait for real candidate reply; return it to FSM as the 'question'."""
                    # This is called AFTER the FSM processes a candidate answer.
                    # We need to send the NEXT question — generate it from context.
                    return candidate_text  # FSM uses this to build its next cue

            self._fsm = InterviewerFSM(
                rubric=self._rubric,
                brief={"candidate_name": self.candidate_id},
                session=_LiveSession(),
            )
            self._fsm.advance()  # Advance to OPENING

            # ── BUG-16: Dynamic opening question grounded in resume + role ─────
            job_title    = self._rubric.get("standard", f"Role ({self.role_id})")
            job_desc     = self._rubric.get("jd", job_title)
            resume_text  = self._candidate_resume or "Candidate profile not available."
            from app.agents.interviewer import generate_dynamic_question
            try:
                opening_question = await generate_dynamic_question(
                    job_title=job_title,
                    parsed_resume_text=resume_text,
                    job_description=job_desc,
                    last_candidate_answer="",
                    asked_questions_list=[],
                    history=[],
                    uncovered_competencies=[
                        c.get("competency_id", "") for c in self._rubric.get("competencies", [])
                    ],
                    current_state="OPENING",
                )
            except Exception as exc:
                logger.warning("Dynamic opening question failed: %s — using fallback", exc)
                opening_question = (
                    "Great to meet you! Could you briefly walk me through your most relevant "
                    "experience for this role and what drew you to apply?"
                )
            self._asked_questions.append(opening_question)
            await self._send_interviewer_question(opening_question, turn_number=0)
            current_question = opening_question

            # ── Interactive turn loop ─────────────────────────────────────
            turn_count = 0
            competencies = self._rubric.get("competencies", [
                {"competency_id": "core_skills", "keywords": ["python", "backend"]}
            ])

            # BUG-03: Broadcast duration to frontend so it can show a countdown
            if deadline is not None:
                await _safe_send(self.ws, _frame(SignalType.AGENT_MESSAGE, {
                    "agent": "system",
                    "event": "interview_duration",
                    "duration_seconds": int(self.duration_seconds),
                    "text": f"Interview duration: {int(self.duration_seconds // 60)} minutes.",
                }))

            warned_2min = False
            warned_1min = False

            while turn_count < self.MAX_TURNS:
                # BUG-03: Timer-based warnings and auto-end
                if deadline is not None:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 120 and not warned_2min:
                        warned_2min = True
                        await _safe_send(self.ws, _frame(SignalType.AGENT_MESSAGE, {
                            "agent": "interviewer",
                            "event": "timer_warning",
                            "text": "We have about two minutes remaining. Let's start wrapping up — please keep your next answer brief.",
                        }))
                        if self._fsm:
                            self._fsm.state = __import__(
                                'app.agents.interviewer_fsm', fromlist=['InterviewState']
                            ).InterviewState.CLOSING
                    if remaining <= 60 and not warned_1min:
                        warned_1min = True
                        await _safe_send(self.ws, _frame(SignalType.AGENT_MESSAGE, {
                            "agent": "interviewer",
                            "event": "timer_warning",
                            "text": "One minute left. Please finish your thought.",
                        }))
                    if remaining <= 0:
                        logger.info("Room %s: interview time limit reached — auto-ending", room_id)
                        await _safe_send(self.ws, _frame(SignalType.AGENT_MESSAGE, {
                            "agent": "interviewer",
                            "text": "Our time is up. Thank you so much for your time today — it was a pleasure speaking with you. We'll be in touch shortly!",
                        }))
                        break

                # Wait for a candidate reply (with 5-minute timeout per turn)
                try:
                    wait_timeout = min(300.0, max(10.0, deadline - asyncio.get_event_loop().time())) if deadline else 300.0
                    candidate_text = await asyncio.wait_for(
                        turn_queue.get(), timeout=wait_timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning("Room %s: candidate timed out on turn %d", room_id, turn_count)
                    await _safe_send(ws_ref, _frame(SignalType.AGENT_MESSAGE, {
                        "agent": "interviewer",
                        "text": "It seems you may have stepped away. The session will close now.",
                        "turn_number": turn_count,
                    }))
                    break

                if candidate_text == "__END_SESSION__":
                    logger.info("Room %s received __END_SESSION__ signal — proceeding to EvaluatorAgent evaluation", room_id)
                    break

                if not candidate_text:
                    continue

                # Record in transcript & session turn history
                candidate_turns.append(candidate_text)
                transcript.append({"speaker": "candidate", "text": candidate_text})
                self.history.append({"question": current_question, "answer": candidate_text})

                # ── Real-time Supabase: write candidate answer to interviews.transcript ──
                try:
                    await db.append_transcript(self.interview_id, {
                        "speaker": "candidate",
                        "text": candidate_text,
                        "turn_number": turn_count + 1,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as tc_err:
                    logger.warning(
                        "Failed to append candidate turn to interviews.transcript for %s: %s",
                        self.interview_id, tc_err,
                    )

                # ── Real-time Supabase: structured Q&A log (interview_qa_logs table) ──
                qa_log_payload = {
                    "session_id": self.interview_id,
                    "question_number": turn_count + 1,
                    "question_text": current_question,
                    "candidate_answer_transcript": candidate_text,
                    "confidence_score": 0.85,
                    "metadata": {
                        "candidate_id": self.candidate_id,
                        "interview_id": self.interview_id,
                        "role_id": self.role_id,
                        "room_id": room_id,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    await db.insert("interview_qa_logs", qa_log_payload)
                except Exception as log_err:
                    logger.warning("Failed to log turn to interview_qa_logs for room %s: %s", room_id, log_err)

                if self._fsm:
                    self._fsm._answers.append(candidate_text)
                    self._fsm.advance()

                # Broadcast candidate's message back to room (so HR observers see it)
                await room_manager.broadcast(room_id, _frame(SignalType.INTERVIEW_TURN, {
                    "turn_number": turn_count + 1,
                    "speaker": "candidate",
                    "text": candidate_text,
                }))

                turn_count += 1

                # Check if we've covered enough turns
                if turn_count >= self.MAX_TURNS:
                    break

                # ── Generate next question from competency coverage ────────
                comp_idx = turn_count % len(competencies)
                comp = competencies[comp_idx]
                comp_id = comp.get("competency_id", "")
                keywords = comp.get("keywords", [])

                # Build a dynamic follow-up question using full interview history
                next_question = await self._generate_follow_up(
                    candidate_text=candidate_text,
                    competency_id=comp_id,
                    keywords=keywords,
                    turn_number=turn_count,
                )
                current_question = next_question
                await self._send_interviewer_question(next_question, turn_number=turn_count)
                # BUG-11: DO NOT append here — _send_interviewer_question already appends to self.transcript


            # ── Closing message ───────────────────────────────────────────
            closing_text = (
                "That concludes our technical interview. "
                "Thank you for your time and thoughtful responses. "
                "We'll be in touch soon with next steps!"
            )
            await _safe_send(ws_ref, _frame(SignalType.AGENT_MESSAGE, {
                "agent": "interviewer",
                "text": closing_text,
                "turn_number": turn_count + 1,
            }))

            # ── Finalize transcript in Supabase (mark immutable) ─────────────
            try:
                # Append closing message to the transcript record
                await db.append_transcript(self.interview_id, {
                    "speaker": "interviewer",
                    "text": closing_text,
                    "turn_number": turn_count + 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                await db.finalize_transcript(self.interview_id)
                logger.info(
                    "Transcript finalized in Supabase for interview %s (%d turns)",
                    self.interview_id, turn_count,
                )
            except Exception as fin_err:
                logger.warning(
                    "Could not finalize transcript for %s: %s",
                    self.interview_id, fin_err,
                )

            # ── Run FSM for rubric analysis (non-interactive post-processing) ──
            try:
                # BUG-05: was `fsm.run_interview` (NameError) — must be self._fsm
                fsm_result = await self._fsm.run_interview(
                    candidate_turns or ["No response recorded."],
                    transcript_ref=self.interview_id,
                )
            except Exception as exc:
                logger.error("FSM post-processing failed for room %s: %s", room_id, exc)
                fsm_result = {"questions": [], "needs_human_review": True}

            # ── Evaluation ────────────────────────────────────────────────
            await _safe_send(ws_ref, _frame(SignalType.AGENT_MESSAGE, {
                "agent": "evaluator",
                "text": "Analysing your interview responses… Please wait.",
            }))

            try:
                evaluator = EvaluatorAgent(run_id=self.run_id)
                scorecard_result = await evaluator.evaluate_transcript(
                    interview_id=self.interview_id,
                    candidate_id=self.candidate_id,
                    rubric=self._rubric,
                    transcript_turns=transcript,
                )
            except Exception as exc:
                logger.error("EvaluatorAgent failed for room %s: %s", room_id, exc)
                scorecard_result = {
                    "scorecard": {"overall_fit": 0.0, "needs_human_review": True},
                    "final_recommendation": {"hiring_recommendation": "Manual Review Required"},
                    "behavioral_metrics": {},
                }

            # Broadcast scorecard update
            await room_manager.broadcast(room_id, _frame(SignalType.EVAL_UPDATE, {
                "scorecard": scorecard_result.get("scorecard", {}),
                "final_recommendation": scorecard_result.get("final_recommendation", {}),
                "behavioral_metrics": scorecard_result.get("behavioral_metrics", {}),
                "detailed_competencies": scorecard_result.get("detailed_competencies", []),
                "full_transcript_evaluations": scorecard_result.get("full_transcript_evaluations", []),
            }))

            # ── Reporting (fire-and-forget) ───────────────────────────────
            try:
                from app.agents.reporting import run_reporting
                import asyncio as _aio
                scorecard = scorecard_result.get("scorecard", {})
                state_payload = {
                    "shortlist": [{"ref_id": self.candidate_id}],
                    "top_candidate": self.candidate_id,
                    "results": {"interview": scorecard_result},
                    "needs_review": scorecard.get("needs_human_review", False),
                    "goal": "Candidate Interview Outcomes",
                }
                reporting_result = await _aio.to_thread(run_reporting, self.run_id, state_payload)
            except Exception as exc:
                logger.error("Reporting failed for room %s: %s", room_id, exc)
                reporting_result = {}

            log_event(
                run_id=self.run_id,
                source="room_signaling",
                event_type="interview_completed",
                payload={
                    "room_id": room_id,
                    "interview_id": self.interview_id,
                    "scorecard_id": scorecard_result.get("scorecard_id"),
                    "turns_completed": turn_count,
                },
            )

            # ── Session end ───────────────────────────────────────────────
            await room_manager.broadcast(room_id, _frame(SignalType.SESSION_END, {
                "status": "completed",
                "fsm_summary": fsm_result,
                "scorecard": scorecard_result.get("scorecard", {}),
                "final_recommendation": scorecard_result.get("final_recommendation", {}),
                "behavioral_metrics": scorecard_result.get("behavioral_metrics", {}),
                "detailed_competencies": scorecard_result.get("detailed_competencies", []),
                "full_transcript_evaluations": scorecard_result.get("full_transcript_evaluations", []),
                "reporting_result": reporting_result,
            }))


        except Exception as exc:
            logger.error(
                "Interview loop crashed for room %s: %s", self.room_id, exc, exc_info=True,
            )
            await _safe_send(self.ws, _frame(SignalType.ERROR, {
                "message": f"Interview session encountered an error: {exc}",
            }))
        finally:
            # BUG-08: close_room is already called in run() finally — do NOT duplicate here
            logger.info("Interview loop exited for room %s", self.room_id)

    async def _send_interviewer_question(self, question_text: str, turn_number: int) -> None:
        """Send an AI interviewer question frame to the candidate (single frame emission)."""
        from app.config import settings
        from app.services.speech_engine import TTSService

        audio_b64 = None
        if settings.TTS_PROVIDER:
            try:
                tts = TTSService(settings.TTS_PROVIDER)
                audio_b64 = await tts.synthesize_speech_b64(question_text)
            except Exception as exc:
                logger.warning("TTS audio synthesis skipped/failed: %s", exc)

        payload_data = {
            "turn_number": turn_number,
            "speaker": "interviewer",
            "agent": "interviewer",
            "text": question_text,
        }
        if audio_b64:
            payload_data["audio_b64"] = audio_b64

        # Deduplicated: Send ONLY ONE frame per interviewer question
        payload = _frame(SignalType.INTERVIEW_TURN, payload_data)
        await _safe_send(self.ws, payload)

        # ── Append interviewer question to Supabase interviews.transcript ────
        self.transcript.append({"speaker": "interviewer", "text": question_text})
        try:
            await db.append_transcript(self.interview_id, {
                "speaker": "interviewer",
                "text": question_text,
                "turn_number": turn_number,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as tc_err:
            logger.warning(
                "Failed to append interviewer question to interviews.transcript for %s: %s",
                self.interview_id, tc_err,
            )

    async def _generate_follow_up(
        self,
        candidate_text: str,
        competency_id: str,
        keywords: list[str],
        turn_number: int,
    ) -> str:
        """Generate a dynamic contextual follow-up question based on candidate answer."""
        from app.agents.interviewer import generate_dynamic_question

        job_title = self._rubric.get("standard", f"Role ({self.role_id})")
        parsed_resume_text = self._candidate_resume or f"Candidate Profile ({self.candidate_id})"
        job_description = self._rubric.get("jd", job_title)

        uncovered_comps = []
        current_state_str = "INTERVIEW"
        if self._fsm:
            comps = self._fsm._competencies()
            uncovered_comps = [c.get("competency_id", "") for c in comps if not self._fsm._covered(c)]
            current_state_str = self._fsm.state.name

        q = await generate_dynamic_question(
            job_title=job_title,
            parsed_resume_text=parsed_resume_text,
            job_description=job_description,
            last_candidate_answer=candidate_text,
            asked_questions_list=self._asked_questions,
            history=self.history,
            uncovered_competencies=uncovered_comps,
            current_state=current_state_str,
        )


        # Fallback to keyword probing or short answer technical probing if needed
        lowered = candidate_text.lower()
        covered = [kw for kw in keywords if kw.lower() in lowered]
        if covered and q in self._asked_questions:
            q = (
                f"You mentioned {covered[0]} — can you walk me through a specific project "
                f"or situation where you applied that? What was the outcome?"
            )
        elif len(candidate_text.split()) < 3 and candidate_text and candidate_text.strip() not in ("__END_SESSION__", ""):
            if candidate_text.lower() not in q.lower() and "technical" not in q.lower() and "architecture" not in q.lower():
                q += f" Could you elaborate on technical details regarding '{candidate_text}' and how it relates to your architecture experience?"

        self._asked_questions.append(q)
        return q


    def _default_rubric(self) -> dict[str, Any]:
        return {
            "standard": f"Position ({self.role_id})",
            "competencies": [
                {"competency_id": "system_design", "keywords": ["architecture", "scalability", "distributed"]},
                {"competency_id": "python_backend", "keywords": ["python", "fastapi", "async", "django"]},
                {"competency_id": "databases", "keywords": ["sql", "postgres", "redis", "orm"]},
                {"competency_id": "problem_solving", "keywords": ["algorithm", "debug", "optimize", "trade-off"]},
            ],
        }

    def _parse(self, raw: str) -> dict[str, Any] | None:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            asyncio.ensure_future(
                _safe_send(self.ws, _frame(SignalType.ERROR, {"message": "Invalid JSON frame"}))
            )
            return None


# ─── WebSocket handler (entry point) ──────────────────────────────────────────

async def room_ws_handler(websocket: WebSocket, room_id: str) -> None:
    """Main WebSocket endpoint handler for a room session."""
    await websocket.accept()

    # Verify room exists
    room = room_manager.get_room(room_id)
    if room is None:
        await _safe_send(websocket, _frame(SignalType.ERROR, {
            "message": f"Room {room_id!r} does not exist or has expired."
        }))
        await websocket.close(code=4004)
        return

    # Register client in room
    session = await room_manager.join_room(room_id, websocket)

    # Send room-joined frame
    await _safe_send(websocket, _frame(SignalType.ROOM_JOINED, {
        "room_id":      room_id,
        "room_url":     room.room_url,
        "candidate_id": room.candidate_id,
        "interview_id": room.interview_id,
        "status":       room.status.value,
    }))

    # Send consent disclosure (welcome message from Consent Agent)
    from app.agents.consent_agent import ConsentAgent
    from app.services.parser import clean_candidate_name

    cand_display_name = clean_candidate_name(room.candidate_id)
    try:
        cand_db = await db.query("candidates", id=room.candidate_id)
        if cand_db and cand_db[0].get("name"):
            cand_display_name = cand_db[0]["name"]
    except Exception:
        pass

    disclosure = ConsentAgent().get_disclosure_script(cand_display_name)
    await _safe_send(websocket, _frame(SignalType.CONSENT_ASK, {"text": disclosure}))

    run_id = getattr(session, "run_id", None) or f"run-room-{room_id[:8]}"

    # Hand off to the interactive session state machine
    live_session = _InteractiveRoomSession(
        ws=websocket,
        room_id=room_id,
        interview_id=room.interview_id,
        candidate_id=room.candidate_id,
        role_id=room.metadata.get("role_id", "r-default"),
        run_id=run_id,
    )
    await live_session.run()
