"""Interview Routes — self-hosted room lifecycle replaces Google Meet."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid

from app.rooms.room_manager import room_manager

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


class DeployBotRequest(BaseModel):
    """Create or join an in-platform interview room."""
    room_id: str | None = None          # Optional: join an existing room
    candidate_id: str
    role_id: str
    interview_id: str | None = None


@router.post("/deploy")
async def deploy_bot(req: DeployBotRequest):
    """
    Create a self-hosted interview room and insert the interview record.

    Replaces the old bot deployment flow. The 'room' IS the interview;
    agents connect directly via WebSocket, no external bot proxy needed.
    """
    try:
        interview_id = req.interview_id or uuid.uuid4().hex

        # If a room_id was provided, validate it exists
        if req.room_id:
            room = room_manager.get_room(req.room_id)
            if room is None:
                raise HTTPException(status_code=404, detail=f"Room {req.room_id!r} not found")
            interview_id = room.interview_id
            room_id = req.room_id
            room_url = room.room_url

        # Persist the canonical interview before creating its runtime room.
        from app.services.database import db
        if not await db.query("candidates", id=req.candidate_id):
            raise HTTPException(status_code=422, detail=f"Unknown candidate_id: {req.candidate_id}")
        if not await db.query("roles", id=req.role_id):
            raise HTTPException(status_code=422, detail=f"Unknown role_id: {req.role_id}")

        existing = await db.query("interviews", id=interview_id)
        if not existing:
            await db.insert("interviews", {
                "id":           interview_id,
                "candidate_id": req.candidate_id,
                "role_id":      req.role_id,
                "transcript":   [],
            })

        if not req.room_id:
            room = await room_manager.create_room(
                candidate_id=req.candidate_id,
                interview_id=interview_id,
                metadata={"role_id": req.role_id},
            )
            room_id = room.room_id
            room_url = room.room_url

        return {
            "status":       "success",
            "message":      "Interview room is ready!",
            "interview_id": interview_id,
            "room_id":      room_id,
            "room_url":     room_url,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create interview room: {str(e)}")


class EndRoomRequest(BaseModel):
    room_id: str


@router.post("/end_room")
async def end_room(req: EndRoomRequest):
    """
    Close an interview room session.
    Idempotent — returns success even if room is already closed.
    """
    try:
        room = room_manager.get_room(req.room_id)
        if room is None:
            return {"status": "success", "message": "Room already closed or does not exist."}
        await room_manager.close_room(req.room_id)
        return {
            "status":  "success",
            "message": "Interview room closed.",
            "room_id": req.room_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to close room: {str(e)}")


class CompleteInterviewRequest(BaseModel):
    candidate_turns: list[str] | None = None


@router.post("/{room_id}/complete")
async def complete_interview(room_id: str, req: CompleteInterviewRequest | None = None):
    """
    Complete WebRTC interview session and trigger evaluation & reporting asynchronously.
    """
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Interview room {room_id!r} not found or already closed.")

    from app.rooms.signaling import _run_agent_pipeline
    from app.agents.reporting import run_reporting
    import asyncio

    candidate_turns = (req.candidate_turns if req else None) or []
    if not any(turn.strip() for turn in candidate_turns):
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "EMPTY_TRANSCRIPT",
                "message": "At least one candidate answer is required before completion.",
            },
        )
    run_id = room.metadata.get("run_id") or f"run-room-{room_id[:8]}"
    role_id = room.metadata.get("role_id", "r-default")

    result = await _run_agent_pipeline(
        room_id=room_id,
        interview_id=room.interview_id,
        candidate_id=room.candidate_id,
        role_id=role_id,
        consent_response="Yes, consent granted.",
        candidate_turns=candidate_turns,
        run_id=run_id,
    )

    if result.get("status") != "completed":
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": "INTERVIEW_PIPELINE_FAILED",
                "result": result,
            },
        )

    scorecard = result.get("scorecard", {})
    needs_review = scorecard.get("scorecard", {}).get("needs_human_review", False)
    state = {
        "shortlist": [{"ref_id": room.candidate_id}],
        "top_candidate": room.candidate_id,
        "results": {"interview": scorecard},
        "needs_review": needs_review,
        "goal": "Candidate Interview Outcomes"
    }

    # Trigger the evaluator agent
    from app.agents.evaluator_agent import EvaluatorAgent
    try:
        evaluator = EvaluatorAgent(run_id=run_id)
        await evaluator.evaluate_transcript(
            interview_id=room.interview_id,
            candidate_id=room.candidate_id,
            rubric=room.metadata.get("rubric")  # If available, else EvaluatorAgent might fetch it or run without
        )
    except Exception as e:
        import logging
        logging.getLogger("talentops.routes").error("EvaluatorAgent failed in complete_interview: %s", e)

    reporting_result = await asyncio.to_thread(run_reporting, run_id, state)
    result["reporting_result"] = reporting_result

    from app.agents.manager_debrief import build_manager_debrief_script, create_manager_debrief_session

    debrief_state = {**state, "report": reporting_result}
    debrief_session = await create_manager_debrief_session(
        interview_id=room.interview_id,
        candidate_id=room.candidate_id,
        run_id=run_id,
        final_state=debrief_state,
    )
    result["manager_debrief"] = {
        **debrief_session,
        "script": build_manager_debrief_script(run_id, debrief_state),
    }

    await room_manager.close_room(room_id)
    return {"status": "success", "room_id": room_id, "result": result}
