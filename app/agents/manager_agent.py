"""Manager Agent escalation rules + pipeline decisions (Task 6.6)."""
from app.services.database import db
from app.services.email_handler import send_email

VALID_REASONS = {"low_confidence", "double_conflict", "no_qualified_candidates",
                 "review_limit_exceeded", "delivery_failure",
                 "protected_attribute_flag", "reschedule_required"}


class ManagerAgent:
    def __init__(self, role_id: str, user_email: str = "manager@example.com") -> None:
        self.role_id = role_id
        self.user_email = user_email

    async def escalate(self, reason: str, details_ref: str | None = None,
                       candidate_id: str | None = None) -> dict:
        if reason not in VALID_REASONS:
            raise ValueError(f"unknown escalation reason {reason!r}")
        payload = {
            "type": "escalation",
            "reason": reason,
            "role_id": self.role_id,
            "details_ref": details_ref,
            "candidate_id": candidate_id,
        }
        event = await db.insert("events", payload)
        await send_email(self.user_email, f"[TalentOps escalation] {reason}",
                         f"Escalation {reason} for role {self.role_id} "
                         f"(candidate: {candidate_id or 'n/a'}, ref: {details_ref or 'n/a'}).")
        if isinstance(event, dict):
            res = dict(payload)
            res.update(event)
            return res
        return payload

    async def on_interviewer_result(self, result: dict) -> dict | None:
        if result.get("needs_human_review"):
            return await self.escalate("low_confidence",
                                       details_ref=result.get("transcript_ref"),
                                       candidate_id=result.get("candidate_id"))
        return None

    async def on_scheduling(self, status: str, conflict_count: int,
                            candidate_id: str | None = None) -> dict | None:
        if conflict_count >= 2 or status == "rejected":
            return await self.escalate("double_conflict", candidate_id=candidate_id)
        return None

    async def on_sourcing_cycle(self, cycles: int, qualified_count: int) -> dict | None:
        if qualified_count == 0 and cycles >= 2:
            return await self.escalate("no_qualified_candidates")
        return None

    async def decide(self, scorecard_result: dict) -> str:
        card = scorecard_result["scorecard"]
        candidate_id = scorecard_result.get("candidate_id")
        if card.get("needs_human_review"):
            await self.escalate("low_confidence", candidate_id=candidate_id)
            return "hold"
        decision = "invite" if card.get("overall_fit", 0.0) >= 0.7 else "reject"
        await send_email(self.user_email, f"[TalentOps decision] {decision}",
                         f"Candidate {candidate_id}: {decision} "
                         f"(fit {card.get('overall_fit'):.2f}).")
        return decision

    async def with_failure_handling(self, coro_fn, *args):
        # covers loss of API connection / session drops (Task 6.6)
        try:
            return await coro_fn(*args)
        except Exception as e:
            await db.insert("events", {"type": "task.error", "role_id": self.role_id,
                                       "error": str(e)})
            raise

    async def get_interview_context(self, interview_id_or_candidate_id: str) -> dict:
        """Fetch all stored evaluations, Q&As, transcripts, and subagent decisions from database."""
        target_id = interview_id_or_candidate_id

        # 1. Fetch scorecard & evaluation report
        scorecards = await db.query("scorecards", interview_id=target_id)
        if not scorecards:
            scorecards = await db.query("scorecards", candidate_id=target_id)
        scorecard_data = scorecards[0] if scorecards else {}

        # 2. Fetch Q&A logs
        qa_logs = await db.query("interview_qa_logs", interview_id=target_id)
        if not qa_logs:
            qa_logs = await db.query("interview_qa_logs", candidate_id=target_id)

        # 3. Fetch interview room & transcript
        rooms = await db.query("interview_rooms", interview_id=target_id)
        if not rooms:
            rooms = await db.query("interview_rooms", candidate_id=target_id)
        room_data = rooms[0] if rooms else {}

        # 4. Fetch candidate details
        cand_id = scorecard_data.get("candidate_id") or room_data.get("candidate_id") or target_id
        candidates = await db.query("candidates", id=cand_id)
        candidate_data = candidates[0] if candidates else {}

        # 5. Fetch subagent decision events
        events = await db.query("events", role_id=self.role_id)
        if not events:
            events = await db.query("events", candidate_id=cand_id)

        return {
            "interview_id": target_id,
            "candidate_id": cand_id,
            "candidate_profile": candidate_data,
            "scorecard": scorecard_data.get("scorecard") or scorecard_data,
            "qa_logs": qa_logs,
            "transcript_turns": room_data.get("turns") or scorecard_data.get("full_transcript_evaluations") or qa_logs,
            "transcript_summary": room_data.get("transcript") or "",
            "subagent_events": events,
        }

    async def answer_interview_question(self, interview_id_or_candidate_id: str, question: str) -> dict:
        """Answer any question regarding the interview using stored evaluations, Q&As, transcript, and subagent decisions.

        The Manager Agent takes explicit accountability for the overall interview and all subagent decisions.
        """
        import logging
        _logger = logging.getLogger("talentops.manager_agent")

        ctx = await self.get_interview_context(interview_id_or_candidate_id)
        card = ctx.get("scorecard", {})
        qa_logs = ctx.get("qa_logs", [])
        turns = ctx.get("transcript_turns", [])
        events = ctx.get("subagent_events", [])
        cand = ctx.get("candidate_profile", {})

        # Keyword & vector matching over Q&A logs & turns
        q_words = [w.lower() for w in question.split() if len(w) > 3]
        relevant_turns = []

        for item in (turns or qa_logs):
            q_text = item.get("question") or item.get("question_text") or ""
            a_text = item.get("candidate_answer") or item.get("answer") or ""
            notes = item.get("evaluator_notes") or item.get("notes") or ""
            combined = f"{q_text} {a_text} {notes}".lower()
            if any(w in combined for w in q_words):
                relevant_turns.append({"question": q_text, "answer": a_text, "evaluator_notes": notes})

        if not relevant_turns and (turns or qa_logs):
            # Take top 3 if keyword search returns nothing
            for item in (turns or qa_logs)[:3]:
                q_text = item.get("question") or item.get("question_text") or ""
                a_text = item.get("candidate_answer") or item.get("answer") or ""
                notes = item.get("evaluator_notes") or item.get("notes") or ""
                relevant_turns.append({"question": q_text, "answer": a_text, "evaluator_notes": notes})

        evidence_str = "\n".join(
            [f"- Q: {t['question']} | A: {t['answer']} | Notes: {t['evaluator_notes']}" for t in relevant_turns]
        ) or "No specific matching Q&A turn recorded."

        manager_prompt = f"""=== ROLE & SUPERVISORY AUTHORITY ===
You are the Manager AI Agent — the central supervisor commanding all sub-agents in the TalentOps hiring pipeline (Sourcing, Screening, Scheduling, Interviewer, Evaluator/Scorecard, and Reporting). You tell every other sub-agent what to do and how to do it. You own all pipeline routing, escalation policies, and final decisions, taking 100% accountability for every sub-agent's actions and outputs.

=== STORED INTERVIEW EVIDENCE & DATABASE RECORDS ===
Hiring Run / Pipeline ID: {self.role_id}
Candidate ID: {ctx.get('candidate_id')}
Candidate Summary: {cand.get('summary', 'N/A')}
Scorecard / Evaluation: {card}
Relevant Q&A & Transcript Evidence:
{evidence_str}
Subagent Decision Events: {events}

=== USER QUESTION ===
{question}

Answer the user's question accurately using the stored interview evidence and subagent decision records above. Explain why and how the sub-agents performed their tasks under your direction, and state clearly that as Manager Agent, you take full ownership and accountability for these decisions.
"""

        try:
            from app.config import settings
            from app.services.llm_clients import openrouter_chat, groq_chat

            messages = [
                {"role": "system", "content": "You are the Manager AI Agent accountable for all interview decisions."},
                {"role": "user", "content": manager_prompt},
            ]
            if settings.LLM_PROVIDER == "groq" and (settings.GROQ_API_KEY or getattr(settings, "GROQ_API_KEY2", "")):
                answer = await groq_chat(messages)
            elif settings.OPENROUTER_API_KEY:
                answer = await openrouter_chat(messages)
            else:
                from app.llm.client import get_llm_client
                client = get_llm_client()
                res = client.complete_json("Manager Agent Accountable QA", manager_prompt, {"answer": "str"})
                answer = res.get("answer", "")
            answer = (answer or "").strip()
        except Exception as exc:
            _logger.warning("LLM synthesis failed in ManagerAgent answer_interview_question: %s", exc)
            answer = (
                f"As the Manager Agent accountable for role '{self.role_id}', I reviewed the stored interview evaluation and transcript. "
                f"Candidate evaluation outcome: fit={card.get('overall_fit', card.get('overall_suitability_score', 'N/A'))}. "
                f"Evidence summary: {evidence_str}"
            )

        accountability_statement = (
            f"As Manager Agent for role '{self.role_id}', I am accountable for the complete interview process "
            f"and all subagent decisions."
        )

        return {
            "role_id": self.role_id,
            "interview_id": interview_id_or_candidate_id,
            "candidate_id": ctx.get("candidate_id"),
            "question": question,
            "answer": answer,
            "accountability_statement": accountability_statement,
            "retrieved_evidence": {
                "scorecard": card,
                "relevant_qa_turns": relevant_turns,
                "total_turns": len(turns or qa_logs),
                "subagent_events": events,
            },
        }


def determine_next_stage(current_stage: str | None, completed: list[str]) -> tuple[str, str]:
    """Determine the next target WorkflowStage and target subagent node."""
    from app.graph.state import WorkflowStage

    if not current_stage or current_stage == WorkflowStage.INTAKE:
        if "intake" not in completed:
            return WorkflowStage.INTAKE, "intake"
        return WorkflowStage.SCREENING, "screening"

    if current_stage == WorkflowStage.SCREENING:
        if "screening" not in completed:
            return WorkflowStage.SCREENING, "screening"
        return WorkflowStage.COORDINATION, "coordination"

    if current_stage == WorkflowStage.COORDINATION:
        if "coordination" not in completed:
            return WorkflowStage.COORDINATION, "coordination"
        return WorkflowStage.ASSESSMENT, "assessment"

    if current_stage == WorkflowStage.WAITING_FOR_ASSESSMENT:
        return WorkflowStage.ASSESSMENT, "assessment"

    if current_stage == WorkflowStage.ASSESSMENT:
        if "assessment" not in completed:
            return WorkflowStage.ASSESSMENT, "assessment"
        return WorkflowStage.EVALUATION, "evaluation"

    if current_stage == WorkflowStage.EVALUATION:
        if "evaluation" not in completed:
            return WorkflowStage.EVALUATION, "evaluation"
        return WorkflowStage.DEBRIEF, "FINISH"

    if current_stage == WorkflowStage.DEBRIEF:
        return WorkflowStage.COMPLETED, "FINISH"

    return WorkflowStage.COMPLETED, "FINISH"
