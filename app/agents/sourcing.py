"""Sourcing sub-agent: Retrieves candidate profiles from the database."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.database import db

logger = logging.getLogger("talentops.sourcing")

async def run_sourcing_async(run_id: str, goal: str, corpus: list[dict] | None = None) -> dict[str, Any]:
    """Async candidate sourcing pipeline: retrieves from database."""
    profiles: list[dict[str, Any]] = []

    if not corpus:
        logger.error("run_sourcing called with no candidate corpus. Supply candidate id via corpus.")
        return {"candidates": [], "count": 0}

    for entry in corpus:
        cand_id = entry.get("id")
        if not cand_id:
            continue

        try:
            # Fetch from database
            cand_records = await db.query("candidates", id=cand_id)
            if not cand_records:
                logger.error("Candidate %s not found in database", cand_id)
                continue

            cand_data = cand_records[0]
            
            # Fetch projects
            proj_records = await db.query("projects", candidate_id=cand_id)
            
            profiles.append({
                "id": cand_id,
                "name": cand_data.get("name") or f"Candidate {cand_id[:6]}",
                "email": cand_data.get("email") or "",
                "phone": cand_data.get("phone") or "",
                "summary": cand_data.get("summary") or "",
                "skills": cand_data.get("skills") or [],
                "projects": proj_records or [],
            })
        except Exception as exc:
            logger.error("Error processing resume candidate '%s' during sourcing: %s", cand_id, exc)
            raise RuntimeError(f"Database error during sourcing candidate {cand_id}: {exc}") from exc

    return {"candidates": profiles, "count": len(profiles)}

def run_sourcing(run_id: str, goal: str, corpus: list[dict] | None = None) -> dict[str, Any]:
    """Sync wrapper for run_sourcing_async."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(run_sourcing_async(run_id, goal, corpus))
        else:
            return loop.run_until_complete(run_sourcing_async(run_id, goal, corpus))
    except Exception:
        return asyncio.run(run_sourcing_async(run_id, goal, corpus))
