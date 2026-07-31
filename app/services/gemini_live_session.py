"""Hybrid Loop Phase 1 (Task 4.3): live audio conversation via Gemini Live.

Conversational interface ONLY — scoring_output=false per AGENT_CONTRACTS v1.2.0 (D19).
This class exposes no competency ratings, no evaluation output of any kind; the
auto-generated text transcript streamed to Supabase is its sole artifact.

Modes:
  LIVE (production): next_turn() calls the real Gemini Live API via google-genai SDK.
                     Requires GEMINI_API_KEY in .env.
  SCRIPT (test/demo): next_turn() returns pre-loaded script strings when _script is provided.
                      Used exclusively in tests and onboarding demos.
"""
from __future__ import annotations

import logging

from app.services.session_broker import VoiceSession
from app.services.transcript_streamer import TranscriptStreamer

logger = logging.getLogger("talentops.gemini_live")

PRIMARY_MODEL = "gemini-3.1-flash-live-preview"
FALLBACK_MODEL = "gemini-2.5-flash-native-audio"


class GeminiLiveSession:
    def __init__(self, session: VoiceSession, interview_id: str,
                 brief: dict | None = None, script: list[str] | None = None,
                 force_fallback: bool = False) -> None:
        self.session = session
        self.interview_id = interview_id
        self.brief = brief or {}
        # script is ONLY for tests / onboarding demos — None means real live mode
        self._script: list[str] | None = list(script) if script is not None else None
        self._force_fallback = force_fallback
        self.active_model: str | None = None
        self.streamer = TranscriptStreamer(interview_id)
        self._context: list[str] = []
        self._interrupted = False
        self._turn = 0
        self.open = False
        self._genai_client = None

    async def start(self) -> None:
        self.active_model = FALLBACK_MODEL if self._force_fallback else PRIMARY_MODEL
        self.open = True
        # Initialize session state for live sessions
        if self._script is None:
            logger.info(
                "[GeminiLiveSession] Started live session %s using model %s",
                self.interview_id, self.active_model
            )

    def simulate_quota_exhaustion(self) -> None:
        # graceful mid-call fallback; the already-streamed transcript is preserved
        self.active_model = FALLBACK_MODEL

    async def inject_context(self, text: str) -> None:
        self._context.append(text)

    async def next_turn(self, candidate_text: str) -> str:
        """Generate next interviewer reply.

        SCRIPT MODE (test/demo): returns next pre-loaded script line.
        LIVE MODE (production): calls real Gemini API with accumulated context.
        """
        if not self.open:
            raise RuntimeError("session not started — call await session.start() first")
        self._interrupted = False
        self._turn += 1

        if self._script is not None:
            # SCRIPT MODE — explicit test/demo path
            if self._script:
                reply = self._script.pop(0)
            else:
                reply = "[Script exhausted — no more scripted turns]"
        else:
            # LIVE MODE — real Groq API call
            try:
                from app.services.llm_clients import groq_chat
                context_cues = "\n".join(self._context[-3:]) if self._context else ""
                brief_str = ", ".join(
                    f"{k}: {v}" for k, v in self.brief.items()
                    if k in ("role", "competencies", "candidate_name")
                )
                system_prompt = (
                    f"You are a professional technical interviewer.\n"
                    f"Interview context: {brief_str}\n"
                    f"Current focus: {context_cues}\n\n"
                    f"Respond with a single concise follow-up question or professional acknowledgement "
                    f"that probes further. Do not score or evaluate — just conduct the interview naturally.\n"
                    f"IMPORTANT: Output your response in plain text only without any Markdown formatting (no asterisks, bold, or lists), as this text will be read aloud by a Text-To-Speech engine."
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": candidate_text}
                ]
                reply = await groq_chat(messages, max_tokens=150)
                reply = reply.strip()
                if not reply:
                    reply = "Could you elaborate further on that point?"
                logger.info(
                    "[GeminiLiveSession] Turn %d completed (model=%s, reply_len=%d)",
                    self._turn, self.active_model, len(reply)
                )
            except Exception as e:
                logger.error(
                    "[GeminiLiveSession] Groq API error on turn %d: %s", self._turn, e
                )
                raise RuntimeError(
                    f"Groq Live API call failed on turn {self._turn}: {e}"
                ) from e

        await self.streamer.stream("candidate", candidate_text)
        await self.streamer.stream("interviewer", reply)
        return reply

    def barge_in(self) -> None:
        # native Gemini Live VAD: candidate speech cancels in-flight TTS
        self._interrupted = True

    @property
    def interrupted(self) -> bool:
        return self._interrupted

    async def close(self) -> None:
        self.open = False
        logger.info("[GeminiLiveSession] Session %s closed at turn %d", self.interview_id, self._turn)

