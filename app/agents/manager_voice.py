"""Manager Agent live reporting — read-only voice Q&A over in-platform rooms."""
import re
import logging
from app.services.database import db
from app.services.session_broker import broker, VoiceSession

logger = logging.getLogger("talentops.manager_voice")

FORBIDDEN = ("change the rubric", "modify", "alter", "re-run", "rerun", "dispatch")
REFUSAL = ("This is a read-only reporting meeting: I can't run sub-agents or alter "
           "rubric/pipeline data mid-meeting. I can answer from the latest pipeline state.")


class ManagerVoiceMeeting:
    def __init__(self, role_id: str, session_factory=None) -> None:
        self.role_id = role_id
        self._session_factory = session_factory
        self.session: VoiceSession | None = None
        self.live = None
        self._room_id: str | None = None
        self._barged = False

    async def start(self, room_id: str) -> dict:
        """Join an in-platform interview room (replaces Google Meet join)."""
        self.session = broker.issue_session("manager", "user")
        self._room_id = room_id
        if self._session_factory:
            self.live = self._session_factory(self.session)
        return {"room_id": self._room_id, "session_id": self.session.session_id}

    async def answer(self, question: str) -> str:
        low = question.lower()
        for term in FORBIDDEN:
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, low):
                return REFUSAL

        db_errors = []
        try:
            candidates = await db.query("candidates", role_id=self.role_id)
        except Exception as exc:
            logger.error("Database query failed for candidates (role_id=%s): %s", self.role_id, exc)
            candidates = None
            db_errors.append("candidates")

        try:
            scorecards = await db.query("scorecards")
        except Exception as exc:
            logger.error("Database query failed for scorecards: %s", exc)
            scorecards = None
            db_errors.append("scorecards")

        try:
            interviews = await db.query("interviews", role_id=self.role_id)
        except Exception as exc:
            logger.error("Database query failed for interviews (role_id=%s): %s", self.role_id, exc)
            interviews = None
            db_errors.append("interviews")

        if db_errors:
            return f"Database query error while fetching pipeline state for {', '.join(db_errors)}. Please retry."

        names = ", ".join(c.get("name", "?") for c in (candidates or [])) or "none yet"
        return (f"Pipeline state: {len(candidates or [])} candidate(s) ({names}); "
                f"{len(interviews or [])} interview(s) recorded; {len(scorecards or [])} scorecard(s) complete.")

    def barge_in(self) -> None:
        self._barged = True  # turn-taking handled natively by VAD

    async def close(self) -> None:
        if self.session:
            broker.close_session(self.session.session_id)
        # Room close is handled by the room_manager, not the voice layer
