"""Manager Agent node + specialized sub-agent nodes.

All five sub-agents have complete implementations. The Manager routes
deterministically and owns all user-facing communication.
"""
from __future__ import annotations

from app.agents.communication import send_invite
from app.agents.interviewer import run_interview
from app.agents.reporting import run_reporting
from app.agents.scheduling import run_scheduling
from app.agents.sourcing import run_sourcing
from app.graph.envelope import make_envelope
from app.graph.state import PipelineState
from app.rubric.rubric import Rubric, generate_rubric
from app.supabase_client import log_event


def manager_node(state: PipelineState) -> dict:
    """Decide which sub-agent runs next (or FINISH) based on explicit WorkflowStage."""
    from app.agents.manager_agent import determine_next_stage

    completed = state.get("completed", [])
    current_stage = state.get("stage")
    next_stage, nxt = determine_next_stage(current_stage, completed)

    log_event(state["run_id"], source="manager", event_type="route",
              payload={"stage": next_stage, "next": nxt, "completed": completed})

    envelope = make_envelope(
        sender="manager",
        recipient=nxt if nxt != "FINISH" else "FINISH",
        kind="dispatch" if nxt != "FINISH" else "finish",
        body={"goal": state["goal"], "stage": next_stage},
    )
    return {"stage": next_stage, "next": nxt, "messages": [envelope]}


def _emit(run_id: str, name: str, result: dict) -> dict:
    log_event(run_id, source=name, event_type="agent_completed", payload=result)
    return make_envelope(sender=name, recipient="manager", kind="result", body=result)


async def intake_node(state: PipelineState) -> dict:
    from app.graph.state import WorkflowStage
    from app.agents.sourcing import run_sourcing_async
    import logging
    run_id = state["run_id"]
    log_event(run_id, source="intake", event_type="agent_started", payload={"goal": state["goal"]})
    
    try:
        result = await run_sourcing_async(run_id, state["goal"], state.get("corpus"))
        rubric = generate_rubric(run_id, state.get("standard") or state["goal"])
    except Exception as e:
        logging.getLogger("talentops.nodes").error("Intake node failed: %s", e)
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": f"Intake failed: {e}", "failed_node": "intake"}}

    log_event(run_id, source="intake", event_type="rubric_frozen",
              payload={"content_hash": rubric.content_hash,
                       "competencies": [c.name for c in rubric.competencies]})

    candidates = result.get("candidates", [])
    if not candidates:
        logging.getLogger("talentops.nodes").error("No valid candidate resume profiles found.")
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": "No valid candidates found.", "failed_node": "intake"}}

    top = candidates[0]["id"]
    # Provide a baseline shortlist since screening will re-evaluate them
    shortlist = [{"ref_id": c.get("id", "cand"), "similarity": 1.0, "coverage_rate": 1.0} for c in candidates]

    env = _emit(run_id, "intake", {"count": result["count"]})
    return {
        "stage": WorkflowStage.SCREENING,
        "completed": ["intake"],
        "candidates": candidates,
        "rubric": rubric.model_dump(),
        "shortlist": shortlist,
        "top_candidate": top,
        "needs_review": False,
        "messages": [env],
    }


def screening_node(state: PipelineState) -> dict:
    from app.graph.state import WorkflowStage
    from app.agents.screening import run_screening
    from app.rubric.rubric import Rubric
    import logging
    
    run_id = state["run_id"]
    log_event(run_id, source="screening", event_type="agent_started", payload={})

    candidates = state.get("candidates", [])
    if not candidates:
        logging.getLogger("talentops.nodes").error("No candidates available for screening")
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": "No candidates available for screening", "failed_node": "screening"}}

    try:
        rubric = Rubric(**state["rubric"])
        result = run_screening(run_id, state["goal"], rubric, candidates=candidates)
    except Exception as e:
        logging.getLogger("talentops.nodes").error("Screening node failed: %s", e)
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": f"Screening failed: {e}", "failed_node": "screening"}}

    shortlist = result.get("shortlist", [])
    if not shortlist:
        logging.getLogger("talentops.nodes").error("Screening produced no viable candidates.")
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": "Screening produced no viable candidates.", "failed_node": "screening"}}

    top = shortlist[0]["ref_id"]

    env = _emit(run_id, "screening", result)
    return {
        "stage": WorkflowStage.COORDINATION,
        "completed": ["screening"],
        "shortlist": shortlist,
        "top_candidate": top,
        "needs_review": result.get("needs_review", False),
        "messages": [env],
    }


async def coordination_node(state: PipelineState) -> dict:
    from app.graph.state import WorkflowStage
    from app.services.database import db
    import logging
    run_id = state["run_id"]
    log_event(run_id, source="coordination", event_type="agent_started", payload={})
    
    top = state.get("top_candidate")
    if not top:
        logging.getLogger("talentops.coordination").error("No top candidate selected for coordination")
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": "No top candidate selected for coordination", "failed_node": "coordination"}}

    candidate_email = None
    if state.get("candidates"):
        for c in state["candidates"]:
            if c.get("id") == top or (isinstance(c.get("id"), str) and c.get("id") in str(top)):
                candidate_email = c.get("email") or (c.get("profile") or {}).get("email")
                break

    if not candidate_email:
        db_cands = await db.query("candidates", id=top)
        if db_cands:
            candidate_email = db_cands[0].get("email") or db_cands[0].get("resume_email")

    try:
        if not candidate_email or "@" not in candidate_email:
            raise ValueError("Candidate email not found in database")
                    
        result = await run_scheduling(run_id, top, candidate_email=candidate_email)

        if result.get("status") == "booked" and top:
            room_url = result.get("room_url")
            invite = await send_invite(
                run_id=run_id, 
                candidate=top, 
                slot="Upcoming", 
                room_url=room_url,
                candidate_email=candidate_email
            )
            result["invite_email"] = invite

    except Exception as e:
        logging.getLogger("talentops.coordination").error("Coordination failed: %s", e)
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": f"Scheduling failed: {e}", "failed_node": "coordination"}}

    env = _emit(run_id, "coordination", result)
    return {
        "stage": WorkflowStage.WAITING_FOR_ASSESSMENT,
        "completed": ["coordination"],
        "results": {"coordination": result},
        "messages": [env],
    }


def assessment_node(state: PipelineState) -> dict:
    from app.graph.state import WorkflowStage
    import logging
    run_id = state["run_id"]
    log_event(run_id, source="assessment", event_type="agent_started",
              payload={"candidate": state.get("top_candidate")})

    top = state.get("top_candidate")
    if not top or not state.get("rubric"):
        logging.getLogger("talentops.assessment").error("No candidate or rubric provided for assessment")
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": "No candidate or rubric provided for assessment", "failed_node": "assessment"}}

    try:
        rubric = Rubric(**state["rubric"])
        result = run_interview(run_id, rubric, top)
    except Exception as e:
        logging.getLogger("talentops.assessment").error("Assessment failed: %s", e)
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": f"Assessment failed: {e}", "failed_node": "assessment"}}

    env = _emit(run_id, "assessment", {
        "candidate": result.get("candidate", top),
        "overall_score": result.get("overall_score", 0.0),
        "coverage_rate": result.get("coverage_rate", 0.0),
        "needs_review": result.get("needs_review", True),
        "status": result.get("status", "completed"),
        "reason": result.get("reason", "")
    })
    return {"stage": WorkflowStage.EVALUATION, "completed": ["assessment"], "results": {"assessment": result}, "messages": [env]}


async def evaluation_node(state: PipelineState) -> dict:
    from app.graph.state import WorkflowStage
    import logging
    run_id = state["run_id"]
    log_event(run_id, source="evaluation", event_type="agent_started", payload={})

    # ── E18 FIX: Trigger the evaluator agent ──
    from app.agents.evaluator_agent import EvaluatorAgent
    top = state.get("top_candidate")
    if not top or not state.get("rubric"):
        logging.getLogger("talentops.nodes").error("No candidate or rubric provided for evaluation")
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": "No candidate or rubric provided for evaluation", "failed_node": "evaluation"}}
    
    # In some flows, interview_id is set in the results. If not, use run_id or top.
    interview_results = state.get("results", {}).get("assessment", {})
    interview_id = interview_results.get("interview_id") or run_id
    
    try:
        evaluator = EvaluatorAgent(run_id=run_id)
        await evaluator.evaluate_transcript(
            interview_id=interview_id,
            candidate_id=top,
            rubric=state.get("rubric")
        )
    except Exception as e:
        logging.getLogger("talentops.nodes").error("EvaluatorAgent failed in evaluation_node: %s", e)
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": f"EvaluatorAgent failed: {e}", "failed_node": "evaluation"}}

    try:
        report = run_reporting(run_id, dict(state))
    except Exception as e:
        logging.getLogger("talentops.nodes").error("run_reporting failed: %s", e)
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": f"run_reporting failed: {e}", "failed_node": "evaluation"}}

    # Generate Manager Debrief room URL & script for Human HR
    try:
        from app.agents.manager_debrief import build_manager_debrief_script, create_manager_debrief_session
        debrief_session = await create_manager_debrief_session(
            interview_id=interview_id, candidate_id=top, run_id=run_id, final_state=dict(state)
        )
        debrief_url = debrief_session.get("room_url") or f"http://localhost:5173/interview/debrief-{interview_id}"
        debrief_script = build_manager_debrief_script(run_id, dict(state))

        manager_debrief = {
            "room_url": debrief_url,
            "meet_link": debrief_url,
            "script": debrief_script,
            "status": "ready",
        }
        report["manager_debrief"] = manager_debrief
    except Exception as e:
        logging.getLogger("talentops.nodes").error("Manager debrief generation failed: %s", e)
        return {"stage": WorkflowStage.DEBRIEF, "needs_review": True, "report": {"error": f"Manager debrief generation failed: {e}", "failed_node": "evaluation"}}

    env = _emit(run_id, "evaluation", {
        "decision": report.get("decision", "ERROR"),
        "emails_sent": len(report.get("emails_sent", [])),
        "needs_human_review": report.get("needs_human_review", True),
        "manager_debrief_link": debrief_url,
    })
    return {"stage": WorkflowStage.DEBRIEF, "completed": ["evaluation"], "report": report, "messages": [env]}


WORKER_NODES = {
    "intake": intake_node,
    "screening": screening_node,
    "coordination": coordination_node,
    "assessment": assessment_node,
    "evaluation": evaluation_node,
}
