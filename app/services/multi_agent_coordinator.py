"""Multi-Agent Coordinator & State Machine Engine for TalentOops In-Platform Interview Rooms.

Orchestrates Consent Agent, Interview Agent, and Evaluator Agent inside a
self-hosted WebSocket room session. Google Meet integration has been removed.
"""
from __future__ import annotations

import logging
from enum import IntEnum
from typing import Any

from app.agents.consent_agent import ConsentAgent
from app.agents.evaluator_agent import EvaluatorAgent
from app.agents.interviewer_fsm import InterviewerFSM
from app.services.database import db
from app.supabase_client import log_event

logger = logging.getLogger("talentops.multi_agent_coordinator")


class RoomSessionState(IntEnum):
    CREATED           = 0
    ROOM_JOINED       = 1
    CONSENT_PENDING   = 2
    CONSENT_GRANTED   = 3
    CONSENT_DENIED    = 4
    INTERVIEW_ACTIVE  = 5
    EVALUATION_COMPLETE = 6


class MultiAgentCoordinator:
    """Coordinator steering Consent, Interview, and Evaluator agents in a room session."""

    def __init__(
        self,
        candidate_id: str,
        role_id: str,
        room_id: str,
        run_id: str = "run-multiagent",
    ):
        if not room_id or not isinstance(room_id, str):
            raise ValueError(f"Invalid room_id: '{room_id}'")

        self.candidate_id  = candidate_id
        self.role_id       = role_id
        self.room_id       = room_id
        self.run_id        = run_id
        self.state         = RoomSessionState.CREATED
        self.interview_id  = f"iv-{candidate_id}-{run_id[:8]}"

        self.consent_agent  = ConsentAgent()
        self.evaluator_agent = EvaluatorAgent(run_id=run_id)

    async def run_session(
        self,
        consent_response_text: str = "Yes, I consent to the recording.",
        candidate_turns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute full multi-agent room workflow with state machine checks."""
        logger.info("Starting Multi-Agent Room session for room: %s", self.room_id)

        # Ensure candidate exists to prevent foreign key violations on scorecard insertion
        try:
            cand = await db.query("candidates", id=self.candidate_id)
            if not cand:
                await db.insert("candidates", {
                    "id": self.candidate_id,
                    "name": f"Unknown Candidate ({self.candidate_id[:8]})",
                    "email": f"{self.candidate_id}@example.com"
                })
        except Exception as e:
            logger.warning("Could not pre-ensure candidate %s: %s", self.candidate_id, e)

        self.state = RoomSessionState.ROOM_JOINED

        # 2. State: ROOM_JOINED → CONSENT_PENDING → CONSENT_GRANTED / CONSENT_DENIED
        self.state = RoomSessionState.CONSENT_PENDING
        consent_result = await self.consent_agent.process_response(
            candidate_id=self.candidate_id,
            response_text=consent_response_text,
            room_id=self.room_id,
            run_id=self.run_id,
        )

        if not consent_result["consent_granted"]:
            self.state = RoomSessionState.CONSENT_DENIED
            logger.warning(
                "Candidate %s denied consent; terminating room session early.",
                self.candidate_id,
            )
            log_event(
                run_id=self.run_id,
                source="multi_agent_coordinator",
                event_type="interview_aborted",
                payload={
                    "candidate_id": self.candidate_id,
                    "interview_id": self.interview_id,
                    "room_id":      self.room_id,
                    "reason":       "consent_refused",
                    "consent_result": consent_result,
                },
            )
            return {
                "interview_id":   self.interview_id,
                "candidate_id":   self.candidate_id,
                "room_id":        self.room_id,
                "state":          self.state.name,
                "consent_granted": False,
                "message":        "Interview terminated early due to consent refusal.",
                "consent_result": consent_result,
            }

        self.state = RoomSessionState.CONSENT_GRANTED

        # 3. State: CONSENT_GRANTED → INTERVIEW_ACTIVE
        self.state = RoomSessionState.INTERVIEW_ACTIVE
        turns = candidate_turns or ["I am experienced with backend engineering and Python."]

        # Look up job rubric from Supabase/DB
        rubrics = await db.query("rubrics", run_id=self.run_id)
        rubric = rubrics[0] if rubrics else {
            "standard": f"Position ({self.role_id})",
            "competencies": [{"competency_id": "core_skills", "keywords": ["python", "backend"]}],
        }

        # Setup Interviewer FSM with async session adapter
        class AsyncSession:
            async def inject_context(self, text: str) -> None:
                pass
            async def next_turn(self, text: str) -> str:
                return f"Tell me more about {text}"

        fsm = InterviewerFSM(
            rubric=rubric,
            brief={"candidate_name": self.candidate_id},
            session=AsyncSession(),
        )

        fsm_result = await fsm.run_interview(turns, transcript_ref=self.interview_id)

        # 4. State: INTERVIEW_ACTIVE → EVALUATION_COMPLETE
        transcript_formatted = [
            {"speaker": "interviewer", "text": "Can you share your background?"},
            {"speaker": "candidate",   "text": " ".join(turns)},
        ]

        scorecard_result = await self.evaluator_agent.evaluate_transcript(
            interview_id=self.interview_id,
            candidate_id=self.candidate_id,
            rubric=rubric,
            transcript_turns=transcript_formatted,
        )

        self.state = RoomSessionState.EVALUATION_COMPLETE

        log_event(
            run_id=self.run_id,
            source="multi_agent_coordinator",
            event_type="session_completed",
            payload={
                "candidate_id": self.candidate_id,
                "interview_id": self.interview_id,
                "room_id":      self.room_id,
                "scorecard_id": scorecard_result.get("scorecard_id"),
            },
        )

        return {
            "interview_id":  self.interview_id,
            "candidate_id":  self.candidate_id,
            "role_id":       self.role_id,
            "room_id":       self.room_id,
            "state":         self.state.name,
            "consent_granted": True,
            "fsm_summary":   fsm_result,
            "scorecard":     scorecard_result["scorecard"],
            "scorecard_id":  scorecard_result.get("scorecard_id"),
        }
