import pytest
from fastapi import HTTPException

from app.api.routes import interviews
from app.rooms.models import InterviewRoom


@pytest.mark.asyncio
async def test_complete_interview_reads_run_id_from_room_metadata(monkeypatch):
    room = InterviewRoom(
        room_id="room-12345678",
        candidate_id="candidate-1",
        interview_id="interview-1",
        room_url="http://localhost/interview/room-12345678",
        metadata={"role_id": "role-1", "run_id": "run-1"},
    )
    captured = {}

    async def fake_pipeline(**kwargs):
        captured.update(kwargs)
        return {"status": "failed", "error": "expected test stop"}

    async def fake_close_room(room_id):
        return {"status": "closed", "room_id": room_id}

    monkeypatch.setattr(interviews.room_manager, "get_room", lambda room_id: room)
    monkeypatch.setattr(interviews.room_manager, "close_room", fake_close_room)

    from app.rooms import signaling

    monkeypatch.setattr(signaling, "_run_agent_pipeline", fake_pipeline)

    with pytest.raises(HTTPException) as exc_info:
        await interviews.complete_interview(
            room.room_id,
            interviews.CompleteInterviewRequest(candidate_turns=["A real answer"]),
        )

    assert captured["run_id"] == "run-1"
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["error_code"] == "INTERVIEW_PIPELINE_FAILED"


@pytest.mark.asyncio
async def test_complete_interview_rejects_missing_candidate_answers(monkeypatch):
    room = InterviewRoom(
        room_id="room-12345678",
        candidate_id="candidate-1",
        interview_id="interview-1",
        room_url="http://localhost/interview/room-12345678",
    )
    monkeypatch.setattr(interviews.room_manager, "get_room", lambda room_id: room)

    with pytest.raises(HTTPException) as exc_info:
        await interviews.complete_interview(room.room_id)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error_code"] == "EMPTY_TRANSCRIPT"


@pytest.mark.asyncio
async def test_deploy_rejects_unknown_role_before_creating_room(monkeypatch):
    created = False

    async def fake_query(table, **filters):
        if table == "candidates":
            return [{"id": filters["id"]}]
        if table == "roles":
            return []
        raise AssertionError(f"Unexpected query: {table}")

    async def fake_create_room(**kwargs):
        nonlocal created
        created = True

    from app.services.database import db

    monkeypatch.setattr(db, "query", fake_query)
    monkeypatch.setattr(interviews.room_manager, "create_room", fake_create_room)

    with pytest.raises(HTTPException) as exc_info:
        await interviews.deploy_bot(interviews.DeployBotRequest(
            candidate_id="candidate-1",
            role_id="missing-role",
            interview_id="interview-1",
        ))

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Unknown role_id: missing-role"
    assert created is False


@pytest.mark.asyncio
async def test_end_room_returns_non_success_when_evaluation_fails(monkeypatch):
    from app.rooms import router as rooms_router

    monkeypatch.setattr(rooms_router.room_manager, "get_room", lambda room_id: object())

    async def fake_close_room(room_id):
        return {
            "status": "EVALUATION_FAILED",
            "room_id": room_id,
            "error_code": "EVALUATION_FAILED",
            "detail": "scorecard persistence failed",
        }

    monkeypatch.setattr(rooms_router.room_manager, "close_room", fake_close_room)

    with pytest.raises(HTTPException) as exc_info:
        await rooms_router.end_room("room-1")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["error_code"] == "EVALUATION_FAILED"


@pytest.mark.asyncio
async def test_end_room_rejects_empty_transcript(monkeypatch):
    from app.rooms import router as rooms_router

    monkeypatch.setattr(rooms_router.room_manager, "get_room", lambda room_id: object())

    async def fake_close_room(room_id):
        return {
            "status": "EVALUATION_FAILED",
            "room_id": room_id,
            "error_code": "EMPTY_TRANSCRIPT",
            "detail": "At least one candidate answer is required before evaluation.",
        }

    monkeypatch.setattr(rooms_router.room_manager, "close_room", fake_close_room)

    with pytest.raises(HTTPException) as exc_info:
        await rooms_router.end_room("room-1")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error_code"] == "EMPTY_TRANSCRIPT"
