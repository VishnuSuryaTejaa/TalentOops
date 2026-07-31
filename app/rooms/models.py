"""Pydantic models for the self-hosted Interview Room system."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RoomStatus(str, Enum):
    SCHEDULED           = "SCHEDULED"
    WAITING             = "WAITING"
    ACTIVE              = "ACTIVE"
    COMPLETED           = "COMPLETED"
    EVALUATION_COMPLETE = "EVALUATION_COMPLETE"
    EVALUATION_FAILED   = "EVALUATION_FAILED"


class InterviewRoom(BaseModel):
    """Runtime state of a single interview room."""
    room_id:      str
    candidate_id: str
    interview_id: str
    room_url:     str
    status:       RoomStatus = RoomStatus.SCHEDULED
    created_at:   datetime   = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at:   datetime | None = None
    ended_at:     datetime | None = None
    metadata:     dict[str, Any]  = Field(default_factory=dict)


class CreateRoomRequest(BaseModel):
    candidate_id:      str
    interview_id:      str
    slot_iso:          str | None = None
    # BUG-15: HR must supply these so the right rubric is loaded in the interview session
    role_id:           str = "r-default"
    run_id:            str | None = None
    # BUG-03: HR sets interview duration (0 = no limit, governed by MAX_TURNS instead)
    duration_minutes:  int = 0
    metadata:          dict[str, Any] = Field(default_factory=dict)


class CreateRoomResponse(BaseModel):
    room_id:  str
    room_url: str
    status:   RoomStatus


# ── WebSocket frame models ────────────────────────────────────────────────────

class SignalType(str, Enum):
    """Types of WebSocket signaling frames exchanged between client and server."""
    # WebRTC negotiation
    OFFER          = "offer"
    ANSWER         = "answer"
    ICE_CANDIDATE  = "ice-candidate"
    # Session lifecycle
    ROOM_JOINED    = "room-joined"
    ROOM_LEFT      = "room-left"
    # Agent pipeline events
    AGENT_MESSAGE  = "agent-message"
    CONSENT_ASK    = "consent-ask"
    CONSENT_RESPONSE = "consent-response"
    INTERVIEW_TURN = "interview-turn"
    EVAL_UPDATE    = "eval-update"
    SESSION_END    = "session-end"
    ERROR          = "error"


class SignalMessage(BaseModel):
    """A single WebSocket frame payload."""
    type:    SignalType
    data:    dict[str, Any] = Field(default_factory=dict)
    room_id: str | None = None
