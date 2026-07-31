"""Screening sub-agent: rank the sourced corpus against the JD + frozen rubric."""
from __future__ import annotations

import logging
from typing import Any

from app.embeddings.embedder import get_embedder
from app.embeddings.store import match, upsert_embedding
from app.graph.confidence import evaluate_confidence
from app.rubric.rubric import Rubric

logger = logging.getLogger("talentops.screening")


def _coverage(rubric: Rubric, candidate: dict[str, Any]) -> dict[str, Any]:
    meta = candidate.get("metadata") or {}
    skills = meta.get("skills") or []
    profile = meta.get("profile") or {}
    summary = profile.get("summary") or ""
    skills_clean = [str(s) for s in skills if s is not None]
    haystack = " ".join([*skills_clean, str(summary)]).lower()
    covered = [c.name for c in rubric.competencies if c.name.lower() in haystack]
    rate = len(covered) / len(rubric.competencies) if rubric.competencies else 0.0
    return {"covered": covered, "rate": round(rate, 3)}


def run_screening(run_id: str, goal: str, rubric: Rubric, candidates: list[dict[str, Any]] | None = None, top_k: int = 3) -> dict[str, Any]:
    if candidates is None:
        candidates = []
        
    embedder = get_embedder()
    jd_vector = embedder.embed(goal)
    upsert_embedding(run_id, kind="jd", ref_id="jd", vector=jd_vector, metadata={"goal": goal})

    for cand in candidates:
        text_to_embed = f"Summary: {cand.get('summary', '')}\nSkills: {', '.join(cand.get('skills') or [])}"
        cand_vector = embedder.embed(text_to_embed)
        upsert_embedding(run_id, kind="candidate", ref_id=cand["id"], vector=cand_vector, metadata={"name": cand.get("name", "")})

    matches = match(run_id, jd_vector, kind="candidate", top_k=top_k)
    
    if not matches and candidates:
        logger.warning("Supabase match returned empty. Proceeding with empty shortlist.")

    shortlist = []
    for m in matches:
        cov = _coverage(rubric, m)
        shortlist.append({
            "ref_id": m["ref_id"],
            "similarity": round(m.get("score", 0.0), 3),
            "coverage_rate": cov["rate"],
            "covered": cov["covered"],
        })

    top_sim = shortlist[0]["similarity"] if shortlist else 0.0
    top_cov = shortlist[0]["coverage_rate"] if shortlist else 0.0
    confidence = round(0.5 * top_sim + 0.5 * top_cov, 3)

    decision = evaluate_confidence(
        run_id, source="screening", confidence=confidence,
        context={"top_candidate": shortlist[0]["ref_id"] if shortlist else None},
    )

    avg_coverage = round(sum(s["coverage_rate"] for s in shortlist) / len(shortlist), 3) if shortlist else 0.0
    return {
        "shortlist": shortlist,
        "rubric_coverage_rate": avg_coverage,
        "confidence": confidence,
        "needs_review": decision.needs_review,
        "reason": decision.reason,
    }
