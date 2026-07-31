import pytest
from unittest.mock import AsyncMock

from app.agents.manager_agent import ManagerAgent
from app.agents.manager_debrief import create_manager_debrief_session, process_hr_debrief_turn
from app.agents.manager_voice import ManagerVoiceMeeting
from app.services.database import db


@pytest.mark.asyncio
async def test_manager_agent_get_interview_context(monkeypatch):
    """Verify get_interview_context queries interview_qa_logs by session_id and normalizes Q&A turns."""
    sample_candidate = {"id": "c-alex", "name": "Alex Candidate", "summary": "Senior Dev"}
    sample_scorecard = {
        "id": "sc-1",
        "interview_id": "iv-100",
        "candidate_id": "c-alex",
        "scorecard": {"overall_fit": 0.85},
        "full_transcript_evaluations": [
            {
                "question": "What is Python GIL?",
                "candidate_answer": "Global Interpreter Lock prevents multi-threading parallelism.",
                "evaluator_notes": "Strong accurate response.",
                "technical_accuracy": 95.0,
            }
        ],
    }
    sample_qa_logs = [
        {
            "session_id": "iv-100",
            "question_number": 1,
            "question_text": "What is Python GIL?",
            "candidate_answer_transcript": "Global Interpreter Lock prevents multi-threading parallelism.",
            "metadata": {"evaluator_notes": "Strong accurate response."},
        }
    ]
    sample_interview = {
        "id": "iv-100",
        "candidate_id": "c-alex",
        "transcript": [
            {"speaker": "interviewer", "text": "What is Python GIL?"},
            {"speaker": "candidate", "text": "Global Interpreter Lock prevents multi-threading parallelism."},
        ],
    }

    async def fake_query(table, **kwargs):
        if table == "scorecards":
            return [sample_scorecard]
        if table == "interview_qa_logs":
            assert kwargs.get("session_id") == "iv-100"
            return sample_qa_logs
        if table == "interviews":
            return [sample_interview]
        if table == "interview_rooms":
            return []
        if table == "candidates":
            return [sample_candidate]
        if table == "events":
            return []
        return []

    monkeypatch.setattr(db, "query", fake_query)

    agent = ManagerAgent(role_id="role-test")
    ctx = await agent.get_interview_context("iv-100")

    assert ctx["interview_id"] == "iv-100"
    assert ctx["candidate_id"] == "c-alex"
    assert ctx["candidate_profile"]["name"] == "Alex Candidate"
    assert len(ctx["transcript_turns"]) == 1
    assert ctx["transcript_turns"][0]["question"] == "What is Python GIL?"
    assert "Global Interpreter Lock" in ctx["transcript_turns"][0]["answer"]


@pytest.mark.asyncio
async def test_manager_agent_answer_interview_question(monkeypatch):
    """Verify answer_interview_question retrieves evidence and generates LLM answer."""
    sample_candidate = {"id": "c-alex", "name": "Alex Candidate", "summary": "Senior Dev"}
    sample_scorecard = {
        "interview_id": "iv-100",
        "candidate_id": "c-alex",
        "full_transcript_evaluations": [
            {
                "question": "How do you handle database indexing?",
                "candidate_answer": "Use B-tree indexes for equality and range queries, composite indexes for multi-column queries.",
                "evaluator_notes": "Solid understanding of B-trees.",
            }
        ],
    }

    async def fake_query(table, **kwargs):
        if table == "scorecards":
            return [sample_scorecard]
        if table == "candidates":
            return [sample_candidate]
        return []

    monkeypatch.setattr(db, "query", fake_query)

    async def fake_groq_chat(messages, **kwargs):
        return "The candidate demonstrated strong knowledge of B-tree indexing for database queries."

    import app.services.llm_clients
    monkeypatch.setattr(app.services.llm_clients, "groq_chat", fake_groq_chat)

    agent = ManagerAgent(role_id="role-test")
    res = await agent.answer_interview_question("iv-100", "What did the candidate say about database indexing?")

    assert res["interview_id"] == "iv-100"
    assert res["candidate_id"] == "c-alex"
    assert "B-tree indexing" in res["answer"]
    assert "accountable" in res["accountability_statement"].lower()
    assert len(res["retrieved_evidence"]["relevant_qa_turns"]) > 0


@pytest.mark.asyncio
async def test_process_hr_debrief_turn_fallback(monkeypatch):
    """Verify process_hr_debrief_turn falls back to querying scorecards/QA logs if session context is thin."""
    sample_session = {
        "interview_id": "iv-200",
        "debrief_id": "debrief-iv-200",
        "knowledge_context": {"candidate_id": "c-alex"},
    }
    sample_scorecard = {
        "interview_id": "iv-200",
        "candidate_id": "c-alex",
        "final_recommendation": {"overall_suitability_score": 90.0, "hiring_recommendation": "Strong Hire"},
        "full_transcript_evaluations": [
            {
                "question": "Explain WebSockets architecture.",
                "candidate_answer": "WebSockets maintain full-duplex TCP connections for real-time messaging.",
                "evaluator_notes": "Excellent explanation.",
            }
        ],
    }

    async def fake_query(table, **kwargs):
        if table == "hr_debrief_sessions":
            return [sample_session]
        return []

    class FakeSelect:
        def __init__(self, table):
            self.table = table
        def eq(self, k, v):
            return self
        def execute(self):
            class _Res:
                data = [sample_scorecard] if self.table == "scorecards" else []
            return _Res()
            
    class FakeSB:
        def table(self, name):
            return FakeSelect(name)

    monkeypatch.setattr(db, "query", fake_query)
    monkeypatch.setattr(db, "_sb", lambda: FakeSB())

    async def fake_groq_chat(messages, **kwargs):
        return "Alex scored 90% and gave an excellent explanation of WebSockets full-duplex TCP connections."

    import app.services.llm_clients
    monkeypatch.setattr(app.services.llm_clients, "groq_chat", fake_groq_chat)

    from app.services.speech_engine import TTSService
    monkeypatch.setattr(TTSService, "synthesize_speech_b64", AsyncMock(return_value="mock_b64_audio"))

    res = await process_hr_debrief_turn("iv-200", "What did Alex say about WebSockets?")

    assert res["interview_id"] == "iv-200"
    assert "WebSockets full-duplex" in res["response_text"]
    assert res["audio_b64"] == "mock_b64_audio"


@pytest.mark.asyncio
async def test_manager_voice_meeting_answer(monkeypatch):
    """Verify ManagerVoiceMeeting.answer delegates to ManagerAgent for LLM Q&A."""
    meeting = ManagerVoiceMeeting(role_id="role-test")
    meeting._room_id = "iv-300"

    async def fake_answer_question(self, interview_id, question):
        return {
            "answer": "As Manager Agent, I confirmed the candidate passed system design with high clarity.",
        }

    monkeypatch.setattr(ManagerAgent, "answer_interview_question", fake_answer_question)

    ans = await meeting.answer("How was the candidate's system design performance?")
    assert "system design with high clarity" in ans


@pytest.mark.asyncio
async def test_evaluator_agent_fetches_supabase_qa(monkeypatch):
    """Verify EvaluatorAgent fetches stored interview_qa_logs from Supabase for real interview evaluation."""
    from app.agents.evaluator_agent import EvaluatorAgent

    sample_room = {
        "room_id": "rm-500",
        "interview_id": "iv-500",
        "candidate_id": "c-alex",
    }
    sample_qa_logs = [
        {
            "session_id": "iv-500",
            "question_number": 1,
            "question_text": "What is the difference between processes and threads?",
            "candidate_answer_transcript": "Processes have separate memory spaces, threads share memory space within a process.",
        }
    ]
    sample_candidate = {"id": "c-alex", "name": "Alex", "summary": "Dev"}

    async def fake_query(table, **kwargs):
        if table == "interview_rooms":
            return [sample_room]
        if table == "interview_qa_logs":
            return sample_qa_logs
        if table == "candidates":
            return [sample_candidate]
        if table == "scorecards":
            return []
        if table == "projects":
            return []
        return []

    async def fake_get_transcript_chunks(interview_id):
        return []

    async def fake_insert(table, payload):
        return {"id": "sc-500", **payload}

    monkeypatch.setattr(db, "query", fake_query)
    monkeypatch.setattr(db, "get_transcript_chunks", fake_get_transcript_chunks)
    monkeypatch.setattr(db, "insert", fake_insert)

    captured_prompt = {}

    async def fake_groq_chat(messages, **kwargs):
        captured_prompt["user"] = messages[1]["content"]
        return """{
            "behavioral_metrics": {"confidence_level": 0.9, "communication_clarity": 0.9, "response_structure": 0.9, "candidate_engagement": 0.9},
            "detailed_competencies": [{"competency_id": "os_fundamentals", "hits_count": 1, "score": 0.95, "technical_accuracy": 95.0, "strengths": ["Accurate definition"], "areas_for_improvement": [], "quotes": ["separate memory spaces"]}],
            "full_transcript_evaluations": [{"question_number": 1, "question": "What is the difference between processes and threads?", "candidate_answer": "Processes have separate memory spaces...", "confidence_score": 0.9, "technical_accuracy": 95.0, "evaluator_notes": "Spot on."}],
            "final_recommendation": {"overall_suitability_score": 95.0, "hiring_recommendation": "Strong Hire", "executive_summary": "Great interview."}
        }"""

    import app.services.llm_clients
    monkeypatch.setattr(app.services.llm_clients, "groq_chat", fake_groq_chat)

    evaluator = EvaluatorAgent(run_id="run-test")
    res = await evaluator.evaluate_transcript(interview_id="rm-500", candidate_id="c-alex")

    assert res["interview_id"] == "iv-500"
    assert res["candidate_id"] == "c-alex"
    assert "processes and threads" in captured_prompt["user"].lower()
    assert res["final_recommendation"]["hiring_recommendation"] == "Strong Hire"
