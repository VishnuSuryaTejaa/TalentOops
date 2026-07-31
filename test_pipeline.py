import asyncio
from app.graph.supervisor import SUPERVISOR
from app.config import settings
from app.services.database import db
import uuid

async def main():
    # Insert a dummy candidate for testing
    cand_id = "test-cand-001"
    cand_email = "candidate@example.com"
    try:
        await db.insert("candidates", {"id": cand_id, "name": "Test Candidate", "email": cand_email, "resume_text": "Sample text", "profile": {"email": cand_email}})
    except Exception:
        pass # Might already exist

    # Run the pipeline
    run_id = f"test-run-{uuid.uuid4().hex[:8]}"
    print(f"Starting run {run_id}")
    
    # We can inject state into the pipeline to test coordination
    from app.graph.state import WorkflowStage
    state = {
        "run_id": run_id,
        "goal": "Test interview",
        "stage": WorkflowStage.COORDINATION,
        "top_candidate": cand_id,
        "candidates": [{"id": cand_id, "name": "Test Candidate", "email": cand_email}],
        "rubric": {"goal": "Test", "competencies": []}
    }
    
    # Run the graph
    config = {"configurable": {"thread_id": run_id}}
    async for event in SUPERVISOR.astream(state, config=config):
        print(event)

if __name__ == "__main__":
    asyncio.run(main())
