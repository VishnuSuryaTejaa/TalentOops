"""In-process Interview Room registry with thread-safe async operations.

Responsibilities
────────────────
- Create and track `InterviewRoom` objects keyed by room_id (UUID).
- Manage connected WebSocket clients per room.
- Persist room state to Supabase (insert on create, update on status change).
- Broadcast JSON frames to all clients in a room.
- Provide a clean `close_room()` path that terminates the agent task.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

from app.rooms.models import InterviewRoom, RoomStatus
from app.services.database import db
from app.supabase_client import log_event

logger = logging.getLogger("talentops.room_manager")


class RoomSession:
    """Runtime container for a single active room."""

    def __init__(self, room: InterviewRoom) -> None:
        self.room = room
        self._clients: set[WebSocket] = set()
        self._lock: asyncio.Lock = asyncio.Lock()
        self.agent_task: asyncio.Task | None = None

    async def add_client(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def remove_client(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send a JSON payload to all connected clients in the room."""
        dead: set[WebSocket] = set()
        async with self._lock:
            clients = set(self._clients)

        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                self._clients -= dead

    def client_count(self) -> int:
        return len(self._clients)


class RoomManager:
    """Singleton registry of all live interview room sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, RoomSession] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    # ── Factory ───────────────────────────────────────────────────────────────

    async def create_room(
        self,
        candidate_id: str,
        interview_id: str,
        run_id: str = "run-manual",
        metadata: dict[str, Any] | None = None,
    ) -> InterviewRoom:
        """Create a new room, persist to Supabase, and register in memory."""
        from app.config import get_settings
        settings = get_settings()

        room_id = str(uuid.uuid4())
        base_url = settings.ROOM_BASE_URL.rstrip("/")
        room_url = f"{base_url}/interview/{room_id}"

        room = InterviewRoom(
            room_id=room_id,
            candidate_id=candidate_id,
            interview_id=interview_id,
            room_url=room_url,
            status=RoomStatus.SCHEDULED,
            metadata=metadata or {},
        )

        # Persist to Supabase
        try:
            await db.insert("interview_rooms", {
                "room_id":      room_id,
                "candidate_id": candidate_id,
                "interview_id": interview_id,
                "room_url":     room_url,
                "status":       RoomStatus.SCHEDULED.value,
                "metadata":     metadata or {},
            })
        except Exception as exc:
            logger.warning("Failed to persist room %s to Supabase: %s", room_id, exc)

        log_event(
            run_id=run_id,
            source="room_manager",
            event_type="room_created",
            payload={"room_id": room_id, "interview_id": interview_id, "room_url": room_url},
        )

        async with self._lock:
            self._sessions[room_id] = RoomSession(room)

        logger.info("Room created: %s → %s", room_id, room_url)
        return room

    # ── Lookup ────────────────────────────────────────────────────────────────

    def get_room(self, room_id: str) -> InterviewRoom | None:
        session = self._sessions.get(room_id)
        return session.room if session else None

    def get_session(self, room_id: str) -> RoomSession | None:
        return self._sessions.get(room_id)

    # ── Client management ─────────────────────────────────────────────────────

    async def join_room(self, room_id: str, ws: WebSocket) -> RoomSession:
        """Register a WebSocket client in the room; transition to WAITING/ACTIVE."""
        session = self._sessions.get(room_id)
        if session is None:
            # Fallback: re-hydrate room session from Supabase database
            try:
                db_rooms = await db.query("interview_rooms", room_id=room_id)
                if db_rooms:
                    r = db_rooms[0]
                    room = InterviewRoom(
                        room_id=r["room_id"],
                        candidate_id=r["candidate_id"],
                        interview_id=r["interview_id"],
                        room_url=r.get("room_url", ""),
                        status=RoomStatus(r.get("status", RoomStatus.SCHEDULED.value)),
                        metadata=r.get("metadata", {}) or {},
                    )
                    async with self._lock:
                        session = RoomSession(room)
                        self._sessions[room_id] = session
                    logger.info("Restored room %s session from database", room_id)
            except Exception as exc:
                logger.warning("Failed to restore room %s from DB: %s", room_id, exc)

        if session is None:
            raise KeyError(f"Room {room_id!r} not found")

        await session.add_client(ws)
        new_status = RoomStatus.WAITING if session.room.status == RoomStatus.SCHEDULED else session.room.status
        await self.update_status(room_id, new_status)
        logger.info("Client joined room %s (total clients: %d)", room_id, session.client_count())
        return session

    async def leave_room(self, room_id: str, ws: WebSocket) -> None:
        session = self._sessions.get(room_id)
        if session:
            await session.remove_client(ws)
            logger.info("Client left room %s (remaining: %d)", room_id, session.client_count())

    # ── State management ──────────────────────────────────────────────────────

    async def update_status(self, room_id: str, status: RoomStatus) -> None:
        session = self._sessions.get(room_id)
        if not session:
            return

        session.room.status = status
        now_utc = datetime.now(timezone.utc)

        # Map internal EVALUATION_COMPLETE status to DB-valid 'COMPLETED' enum
        db_status = "COMPLETED" if status == RoomStatus.EVALUATION_COMPLETE else status.value
        update_data: dict[str, Any] = {"status": db_status}
        if status == RoomStatus.ACTIVE and not session.room.started_at:
            session.room.started_at = now_utc
            update_data["started_at"] = now_utc.isoformat()
        elif status in (RoomStatus.COMPLETED, RoomStatus.EVALUATION_COMPLETE) and not session.room.ended_at:
            session.room.ended_at = now_utc
            update_data["ended_at"] = now_utc.isoformat()

        try:
            await db.update("interview_rooms", {"room_id": room_id}, update_data)
        except Exception as exc:
            logger.warning("Failed to persist room status update for %s: %s", room_id, exc)

    # ── Broadcast ─────────────────────────────────────────────────────────────

    async def broadcast(self, room_id: str, payload: dict[str, Any]) -> None:
        session = self._sessions.get(room_id)
        if session:
            await session.broadcast(payload)

    # ── Teardown ──────────────────────────────────────────────────────────────

    async def close_room(self, room_id: str) -> dict[str, Any]:
        """Complete a room session, run EvaluatorAgent on stored transcript, and clean up state."""
        session = self._sessions.get(room_id)
        room = session.room if session else None

        if not room:
            try:
                db_rooms = await db.query("interview_rooms", room_id=room_id)
                if db_rooms:
                    r = db_rooms[0]
                    room = InterviewRoom(
                        room_id=r["room_id"],
                        candidate_id=r["candidate_id"],
                        interview_id=r["interview_id"],
                        room_url=r.get("room_url", ""),
                        status=RoomStatus(r.get("status", RoomStatus.COMPLETED.value)),
                        metadata=r.get("metadata", {}) or {},
                    )
            except Exception as exc:
                logger.warning("Failed to fetch room %s from DB: %s", room_id, exc)

        if not room:
            logger.warning("Room %s not found for closing", room_id)
            return {"status": "room_not_found", "room_id": room_id}

        # Cancel any running agent task in memory
        if session and session.agent_task and not session.agent_task.done():
            session.agent_task.cancel()
            try:
                await session.agent_task
            except asyncio.CancelledError:
                pass

        # Check if scorecard already generated for this interview_id, room_id, or candidate_id
        already_evaluated = False
        scorecard_result: dict[str, Any] = {}
        try:
            existing_sc = await db.query("scorecards", interview_id=room.interview_id)
            if not existing_sc:
                existing_sc = await db.query("scorecards", interview_id=room_id)
            if not existing_sc:
                existing_sc = await db.query("scorecards", candidate_id=room.candidate_id)
            if existing_sc:
                already_evaluated = True
                scorecard_result = existing_sc[0]
        except Exception as exc:
            logger.warning("Error checking scorecards for %s: %s", room.interview_id, exc)

        if not already_evaluated:
            # 1. Retrieve all Q&A transcript turns from Supabase interview_qa_logs
            qa_logs = []
            try:
                qa_logs = await db.query("interview_qa_logs", session_id=room_id)
                if not qa_logs:
                    qa_logs = await db.query("interview_qa_logs", session_id=room.interview_id)
            except Exception as exc:
                logger.warning("Failed querying interview_qa_logs for room %s: %s", room_id, exc)

            live_transcript_turns: list[dict[str, Any]] = []
            if qa_logs:
                sorted_logs = sorted(qa_logs, key=lambda x: x.get("question_number", 0))
                for log in sorted_logs:
                    q_text = log.get("question_text", "")
                    c_text = log.get("candidate_answer_transcript", "")
                    if q_text:
                        live_transcript_turns.append({"speaker": "interviewer", "text": q_text})
                    if c_text:
                        live_transcript_turns.append({"speaker": "candidate", "text": c_text})

            # Fallback to session.transcript if live_transcript_turns is empty
            if not live_transcript_turns and session and hasattr(session, "transcript") and session.transcript:
                live_transcript_turns = session.transcript

            candidate_answers = [
                turn for turn in live_transcript_turns
                if turn.get("speaker", "").lower() == "candidate" and turn.get("text", "").strip()
            ]
            if not candidate_answers:
                room.status = RoomStatus.EVALUATION_FAILED
                return {
                    "status": RoomStatus.EVALUATION_FAILED.value,
                    "room_id": room_id,
                    "error_code": "EMPTY_TRANSCRIPT",
                    "detail": "At least one candidate answer is required before evaluation.",
                }

            # 2. Retrieve rubric
            rubric = room.metadata.get("rubric", {})
            if not rubric:
                try:
                    run_id = room.metadata.get("run_id", f"run-room-{room_id[:8]}")
                    rubric_db = await db.query("rubrics", run_id=run_id)
                    if rubric_db:
                        rubric = rubric_db[0].get("rubric", {})
                except Exception:
                    pass

            if not rubric:
                rubric = {
                    "standard": f"Role ({room.metadata.get('role_id', 'r-default')})",
                    "competencies": [
                        {"competency_id": "core_skills", "keywords": ["python", "backend", "fastapi", "architecture"]},
                        {"competency_id": "problem_solving", "keywords": ["algorithm", "system", "design", "scale"]},
                    ],
                }

            # 3. Asynchronously invoke EvaluatorAgent
            try:
                from app.agents.evaluator_agent import EvaluatorAgent
                evaluator = EvaluatorAgent(run_id=room.metadata.get("run_id", "run-eval"))
                scorecard_result = await evaluator.evaluate_transcript(
                    interview_id=room.interview_id,
                    candidate_id=room.candidate_id,
                    rubric=rubric,
                    transcript_turns=live_transcript_turns,
                )
            except Exception as eval_exc:
                logger.error("EvaluatorAgent failed during close_room for %s: %s", room_id, eval_exc)
                room.status = RoomStatus.EVALUATION_FAILED
                error_message = str(eval_exc)
                if session:
                    await session.broadcast({
                        "type": "session-end",
                        "data": {
                            "room_id": room_id,
                            "status": RoomStatus.EVALUATION_FAILED.value,
                            "error_code": "EVALUATION_FAILED",
                        },
                    })
                return {
                    "status": RoomStatus.EVALUATION_FAILED.value,
                    "room_id": room_id,
                    "error_code": "EVALUATION_FAILED",
                    "detail": error_message,
                }

        await self.update_status(room_id, RoomStatus.EVALUATION_COMPLETE)

        # Notify all clients the session has ended
        if session:
            await session.broadcast({
                "type": "session-end",
                "data": {
                    "room_id": room_id,
                    "status": "EVALUATION_COMPLETE",
                    "scorecard": scorecard_result.get("scorecard", {}),
                }
            })
            async with self._lock:
                self._sessions.pop(room_id, None)

        logger.info("Room closed and evaluation complete: %s", room_id)
        return {
            "status": "EVALUATION_COMPLETE",
            "room_id": room_id,
            "scorecard": scorecard_result.get("scorecard", {}),
        }


# Singleton instance shared across the application
room_manager = RoomManager()
