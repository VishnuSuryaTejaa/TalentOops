"""Oral Interview Agent Engine: STT/TTS pipeline + Adaptive Q&A + Real-Time Supabase Logging."""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Any

from app.services.conversation_manager import ConversationManager
from app.services.database import db
from app.services.speech_engine import STTService, TTSService
from app.supabase_client import log_event

logger = logging.getLogger("talentops.oral_interview_agent")

_active_managers: dict[str, ConversationManager] = {}


def get_conversation_manager(
    session_id: str, job_description: str = "", parsed_resume: str = ""
) -> ConversationManager:
    if session_id not in _active_managers:
        _active_managers[session_id] = ConversationManager(
            session_id=session_id,
            job_description=job_description,
            parsed_resume=parsed_resume,
        )
    return _active_managers[session_id]


class OralInterviewAgent:
    """Oral speech-based interview agent conducting turn-taking Q&A with real-time Supabase persistence."""

    def __init__(self):
        from app.config import get_settings
        _settings = get_settings()
        self.stt = STTService(provider=_settings.stt_provider)
        self.tts = TTSService(provider=_settings.tts_provider)

    async def process_turn(
        self,
        session_id: str,
        candidate_id: str,
        role_id: str,
        candidate_text: str | None = None,
        candidate_audio_b64: str | None = None,
        run_id: str = "run-oral",
    ) -> dict[str, Any]:
        """Process a single oral interview turn."""
        # 1. Transcribe audio input if provided
        transcript = candidate_text or ""
        if not transcript and candidate_audio_b64:
            try:
                raw_audio = base64.b64decode(candidate_audio_b64)
                transcript = await self.stt.transcribe_audio(raw_audio)
            except Exception as e:
                logger.error("Failed to decode or transcribe audio b64: %s", e)
                transcript = "[Audio transcription unparseable]"

        if not transcript:
            raise ValueError("No transcript provided or audio unparseable.")

        # 2. Retrieve Candidate Resume & Projects from Supabase DB
        candidates = await db.query("candidates", id=candidate_id)
        candidate_resume = ""
        if candidates:
            c = candidates[0]
            cand_name = c.get("name") or candidate_id
            cand_email = c.get("email") or ""
            cand_phone = c.get("phone") or ""
            cand_summary = c.get("summary") or ""
            cand_skills = c.get("skills") or []
            cand_raw = c.get("raw_text") or c.get("resume") or ""

            proj_rows = await db.query("projects", candidate_id=candidate_id)
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
            candidate_resume = "\n\n".join(b for b in resume_blocks if b)

        roles = await db.query("roles", id=role_id)
        job_description = roles[0].get("jd", "") if roles else ""

        # 3. Retrieve ConversationManager instance
        cm = get_conversation_manager(
            session_id=session_id,
            job_description=job_description,
            parsed_resume=candidate_resume,
        )

        # 4. Generate next context-aware question
        question_text = await cm.generate_next_question(candidate_text=transcript)
        question_number = cm.turn_count

        # 5. Synthesize TTS audio response
        audio_b64 = await self.tts.synthesize_speech_b64(question_text)

        # 6. Real-time Supabase Q&A log persistence (interview_qa_logs table)
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        qa_log_payload = {
            "session_id": session_id,
            "question_number": question_number,
            "question_text": question_text,
            "candidate_answer_transcript": transcript,
            "confidence_score": None,
            "metadata": {
                "candidate_id": candidate_id,
                "role_id": role_id,
                "text_length": len(transcript),
            },
            "timestamp": timestamp_iso,
        }

        log_id = f"log-{session_id}-{question_number}"
        stored_log = await db.insert("interview_qa_logs", qa_log_payload)
        if stored_log and isinstance(stored_log, dict) and stored_log.get("id"):
            log_id = stored_log["id"]
        # 7. Audit log event
        log_event(
            run_id=run_id,
            source="oral_interview_agent",
            event_type="qa_turn_completed",
            payload={
                "session_id": session_id,
                "question_number": question_number,
                "candidate_id": candidate_id,
                "qa_log_id": log_id,
            },
        )

        logger.info(
            "OralInterviewAgent turn %d complete for session %s (candidate: %s)",
            question_number, session_id, candidate_id
        )

        return {
            "session_id": session_id,
            "question_number": question_number,
            "question_text": question_text,
            "candidate_answer": transcript,
            "audio_b64": audio_b64,
            "qa_log_id": log_id,
            "timestamp": timestamp_iso,
        }
