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
async def end_room(room_id: str) -> dict[str, Any]:
    """Close a room session, evaluate stored transcript, generate scorecard, and transition status (idempotent)."""
    from app.services.database import db
    room = room_manager.get_room(room_id)
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
