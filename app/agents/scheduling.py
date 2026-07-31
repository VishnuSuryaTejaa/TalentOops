"""Scheduling sub-agent: create a self-hosted TalentOops interview room for the top candidate.

Replaces the previous Google Calendar / Google Meet booking flow.
Room creation is handled by app.rooms.room_manager.
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.database import db

logger = logging.getLogger("talentops.scheduling")


async def run_scheduling(
    run_id: str,
    top_candidate: str | None,
    candidate_email: str | None = None,
    duration_min: int = 45,
) -> dict[str, Any]:
    """Create an interview room for the top candidate and return room details."""
    if not top_candidate:
        raise ValueError("No top candidate provided for scheduling")

    # Resolve candidate_id — preserve exact ID to match database records
    candidate_id = top_candidate

    # Resolve candidate email if not provided
    resolved_email = candidate_email
    if not resolved_email or "@" not in resolved_email:
        candidates = await db.query("candidates", id=top_candidate)
        if not candidates:
            candidates = await db.query("candidates", id=candidate_id)
        if candidates:
            resolved_email = candidates[0].get("email") or candidates[0].get("resume_email")

    if not resolved_email or "@" not in resolved_email:
        logger.error("Candidate email not found in database for candidate: %s", top_candidate)
        raise ValueError("Candidate email not found in database")

    from app.rooms.room_manager import room_manager

    import uuid
    interview_id = str(uuid.uuid4())

    room = await room_manager.create_room(
        candidate_id=candidate_id,
        interview_id=interview_id,
        run_id=run_id,
        metadata={"duration_min": duration_min, "candidate_email": resolved_email},
    )

    logger.info(
        "Interview room created for candidate %s: %s",
        top_candidate, room.room_url,
    )

    return {
        "status": "booked",
        "candidate_id": candidate_id,
        "candidate_email": resolved_email,
        "interview_id": interview_id,
        "room_id": room.room_id,
        "room_url": room.room_url,
    }
