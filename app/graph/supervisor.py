"""LangGraph supervisor graph wiring the Manager to its sub-agents."""
from __future__ import annotations

import uuid

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import WORKER_NODES, manager_node
from app.graph.state import SUB_AGENTS, PipelineState
from app.supabase_client import log_event


def build_graph():
    """Construct and compile the supervisor StateGraph."""
    graph = StateGraph(PipelineState)

    graph.add_node("manager", manager_node)
    for name, node in WORKER_NODES.items():
        graph.add_node(name, node)

    graph.add_edge(START, "manager")

    route_map = {name: name for name in SUB_AGENTS}
    route_map["FINISH"] = END
    graph.add_conditional_edges("manager", lambda s: s["next"], route_map)

    for name in SUB_AGENTS:
        graph.add_edge(name, "manager")

    return graph.compile()


SUPERVISOR = build_graph()


async def run_pipeline(goal: str, standard: str | None = None, corpus: list[dict] | None = None) -> dict:
    """Execute one full pipeline run and return the final state."""
    run_id = str(uuid.uuid4())
    log_event(run_id, source="manager", event_type="run_started",
              payload={"goal": goal, "standard": standard})

    # Persist frozen rubric into DB for this run_id
    from app.services.database import db
    try:
        await db.insert("rubrics", {
            "run_id": run_id,
            "role_title": goal,
            "standard": standard or goal,
            "competencies": [
                {"competency_id": "system_design", "keywords": ["architecture", "scaling", "distributed", "system"]},
                {"competency_id": "python_backend", "keywords": ["python", "fastapi", "async", "django", "api"]},
                {"competency_id": "databases", "keywords": ["sql", "postgres", "redis", "query", "orm"]},
                {"competency_id": "problem_solving", "keywords": ["algorithm", "debug", "performance", "trade-off"]}
            ],
            "difficulty_level": "L2"
        })
    except Exception as e:
        import logging
        logging.getLogger("talentops.supervisor").error("Failed to insert rubric: %s", e)
        raise RuntimeError("Failed to persist rubric to database") from e

    from app.graph.state import WorkflowStage
    initial: PipelineState = {
        "run_id": run_id,
        "goal": goal,
        "standard": standard or goal,
        "stage": WorkflowStage.INTAKE,
        "next": "",
        "completed": [],
        "messages": [],
        "corpus": corpus,
    }
    final_state = await SUPERVISOR.ainvoke(initial)

    log_event(
        run_id,
        source="manager",
        event_type="run_completed",
        payload={
            "completed": final_state.get("completed", []),
            "top_candidate": final_state.get("top_candidate"),
            "needs_review": final_state.get("needs_review", False),
        },
    )
    return {"run_id": run_id, "final_state": final_state}

import json
async def run_pipeline_stream(goal: str, standard: str | None = None, corpus: list[dict] | None = None):
    """Execute pipeline run as an async generator yielding NDJSON for real-time frontend updates."""
    run_id = str(uuid.uuid4())
    log_event(run_id, source="manager", event_type="run_started",
              payload={"goal": goal, "standard": standard})

    from app.services.database import db
    try:
        await db.insert("rubrics", {
            "run_id": run_id,
            "role_title": goal,
            "standard": standard or goal,
            "competencies": [
                {"competency_id": "system_design", "keywords": ["architecture", "scaling", "distributed", "system"]},
                {"competency_id": "python_backend", "keywords": ["python", "fastapi", "async", "django", "api"]},
                {"competency_id": "databases", "keywords": ["sql", "postgres", "redis", "query", "orm"]},
                {"competency_id": "problem_solving", "keywords": ["algorithm", "debug", "performance", "trade-off"]}
            ],
            "difficulty_level": "L2"
        })
    except Exception as e:
        import logging
        logging.getLogger("talentops.supervisor").error("Failed to insert rubric: %s", e)
        raise RuntimeError("Failed to persist rubric to database") from e

    from app.graph.state import WorkflowStage
    initial: PipelineState = {
        "run_id": run_id,
        "goal": goal,
        "standard": standard or goal,
        "stage": WorkflowStage.INTAKE,
        "next": "",
        "completed": [],
        "messages": [],
        "corpus": corpus,
    }
    
    # Optional delay for visual tracking if execution is too fast
    import asyncio
    
    try:
        async for s in SUPERVISOR.astream(initial):
            # Each 's' is a dict mapping node_name -> state update
            # We can extract the latest state by combining them or just yielding the raw event.
            # Usually it's single key dict, e.g. {'manager': {...}}
            node_name = list(s.keys())[0]
            state_update = s[node_name]
            
            payload = {
                "type": "update", 
                "node": node_name,
                "stage": state_update.get("stage", "unknown"),
                "next": state_update.get("next", "")
            }
            
            if "candidates" in state_update:
                payload["candidates"] = state_update["candidates"]
            if "top_candidate" in state_update:
                payload["top_candidate"] = state_update["top_candidate"]
                
            yield json.dumps(payload) + "\n"
            
            # Artificial delay for frontend visual tracking
            await asyncio.sleep(1.0)
            
            final_state = state_update
    except Exception as e:
        yield json.dumps({"type": "error", "error": str(e)}) + "\n"
        return

    # In LangGraph, the final output might be yielded directly or just the last state update.
    # We will just yield a completion event.
    
    log_event(
        run_id,
        source="manager",
        event_type="run_completed",
        payload={
            "completed": final_state.get("completed", []),
            "top_candidate": final_state.get("top_candidate"),
            "needs_review": final_state.get("needs_review", False),
        },
    )
    yield json.dumps({"type": "complete", "run_id": run_id, "final_state": final_state}) + "\n"

