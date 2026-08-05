"""FastAPI router for Interview Room REST endpoints.

Routes
──────
POST /rooms/create           — create a room, get back room_id + room_url
GET  /rooms/{room_id}        — fetch current room status
POST /rooms/{room_id}/end    — close a room (HR or system)
WS   /ws/room/{room_id}      — WebSocket session (mounted in main.py)
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket

from app.rooms.models import CreateRoomRequest, CreateRoomResponse, RoomStatus
from app.rooms.room_manager import room_manager
from app.rooms.signaling import room_ws_handler

logger = logging.getLogger("talentops.rooms_router")

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.post("/create", response_model=CreateRoomResponse)
async def create_room(req: CreateRoomRequest) -> dict[str, Any]:
    """Create a new self-hosted interview room and return its URL."""
    import uuid as _uuid
    resolved_run_id = req.run_id or f"run-room-{_uuid.uuid4().hex[:8]}"
    room = await room_manager.create_room(
        candidate_id=req.candidate_id,
        interview_id=req.interview_id,
        run_id=resolved_run_id,
        metadata={
            "slot_iso":          req.slot_iso,
            # BUG-15/20: persist role_id, run_id, duration so session reads them correctly
            "role_id":           req.role_id,
            "run_id":            resolved_run_id,
            "duration_minutes":  req.duration_minutes,
            **(req.metadata or {}),
        },
    )
    return {
        "room_id":  room.room_id,
        "room_url": room.room_url,
        "status":   room.status,
    }


@router.get("/{room_id}")
async def get_room(room_id: str) -> dict[str, Any]:
    """Return current room metadata and status."""
    room = room_manager.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail=f"Room {room_id!r} not found")
    return room.model_dump()


@router.post("/{room_id}/end")
async def end_room(room_id: str, ended_by: str = "system") -> dict[str, Any]:
    """Close a room session.

    When ended_by='candidate', we record USER_ENDED immediately and skip
    the full EvaluatorAgent run (which requires a complete transcript).
    When ended_by='hr' or 'system', we run the full evaluation pipeline.
    """
    from app.services.database import db
    from app.rooms.models import RoomStatus

    room = room_manager.get_room(room_id)

    # ── Candidate explicitly ended the room ───────────────────────────────────
    if ended_by == "candidate":
        # Update DB status to USER_ENDED regardless of session state
        now_utc_iso = __import__("datetime").datetime.utcnow().isoformat()
        try:
            await db.update(
                "interview_rooms",
                {"room_id": room_id},
                {
                    "status":   "COMPLETED",          # DB enum stays COMPLETED
                    "ended_at": now_utc_iso,
                    "metadata": {"ended_by": "candidate", "end_reason": "user_terminated"},
                },
            )
        except Exception as exc:
            logger.warning("Failed to persist USER_ENDED for room %s: %s", room_id, exc)

        # Cancel any running agent task and remove session
        session = room_manager._sessions.get(room_id)
        if session:
            if session.agent_task and not session.agent_task.done():
                session.agent_task.cancel()
                try:
                    await session.agent_task
                except Exception:
                    pass
            # Notify any remaining WS clients
            try:
                await session.broadcast({
                    "type": "session-end",
                    "data": {
                        "room_id":   room_id,
                        "status":    "USER_ENDED",
                        "ended_by":  "candidate",
                    },
                })
            except Exception:
                pass
            async with room_manager._lock:
                room_manager._sessions.pop(room_id, None)

        logger.info("Room %s ended by candidate — recorded USER_ENDED", room_id)
        return {"status": "USER_ENDED", "room_id": room_id, "ended_by": "candidate"}

    # ── System / HR full evaluation path ─────────────────────────────────────
    if room is None:
        try:
            db_rooms = await db.query("interview_rooms", room_id=room_id)
            if not db_rooms:
                return {"status": "already_closed", "room_id": room_id}
        except Exception:
            return {"status": "already_closed", "room_id": room_id}

    res = await room_manager.close_room(room_id)
    if res.get("status") == RoomStatus.EVALUATION_FAILED.value:
        status_code = 422 if res.get("error_code") == "EMPTY_TRANSCRIPT" else 502
        raise HTTPException(status_code=status_code, detail=res)
    return res


# WebSocket endpoint — registered separately in main.py so FastAPI can handle
# the WebSocket upgrade path outside the router prefix.
async def ws_room_endpoint(websocket: WebSocket, room_id: str) -> None:
    await room_ws_handler(websocket, room_id)
