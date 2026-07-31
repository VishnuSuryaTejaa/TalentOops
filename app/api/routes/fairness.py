"""Fairness & Bias Lens aggregation (Task 6.5): k-anonymized cohort heatmap."""
from typing import Any
from fastapi import APIRouter

from app.config import settings
from app.services.database import db

router = APIRouter()
DRIFT_THRESHOLD = 0.75


@router.get("/api/fairness/heatmap")
async def heatmap(role_id: str, k: int = settings.K_ANONYMITY) -> dict:
    demographics = await db.query("demographics")
    interviews = await db.query("interviews", role_id=role_id)
    # mean question difficulty per candidate (aggregate-only — no ids leave here)
    diff_by_candidate: dict[str, float] = {}
    all_diffs: list[float] = []
    for iv in interviews:
        diffs = [q["difficulty_estimate"] for q in iv.get("questions", [])
                 if q.get("difficulty_estimate") is not None]
        if diffs:
            diff_by_candidate[iv["candidate_id"]] = sum(diffs) / len(diffs)
            all_diffs.extend(diffs)
    overall = sum(all_diffs) / len(all_diffs) if all_diffs else 0.0

    cohorts: dict[tuple[str, str], list[float]] = {}
    for row in demographics:
        candidate_id = row.get("candidate_id")
        d = diff_by_candidate.get(str(candidate_id) if candidate_id else "")
        if d is None:
            continue
        for dimension, value in (row.get("cohort") or {}).items():
            cohorts.setdefault((dimension, str(value)), []).append(d)

    from app.services.fairness import calculate_k_anonymity
    res = calculate_k_anonymity(cohorts, k=k)
    return {"role_id": role_id, **res}
