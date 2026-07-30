"""Shared state that flows through the supervisor graph."""
from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, TypedDict


class WorkflowStage(str, Enum):
    """Canonical recruitment lifecycle states."""
    INTAKE = "INTAKE"
    SCREENING = "SCREENING"
    COORDINATION = "COORDINATION"
    WAITING_FOR_ASSESSMENT = "WAITING_FOR_ASSESSMENT"
    ASSESSMENT = "ASSESSMENT"
    EVALUATION = "EVALUATION"
    DEBRIEF = "DEBRIEF"
    COMPLETED = "COMPLETED"


SUB_AGENTS: list[str] = [
    "intake",
    "screening",
    "coordination",
    "assessment",
    "evaluation",
]


class PipelineState(TypedDict, total=False):
    """State object passed between the manager and its sub-agents."""

    run_id: str
    goal: str
    standard: str
    stage: WorkflowStage
    next: str
    completed: Annotated[list[str], operator.add]
    messages: Annotated[list[dict], operator.add]

    # --- Working data ---
    rubric: dict[str, Any]
    candidates: list[dict]
    shortlist: list[dict]
    top_candidate: dict | None
    needs_review: bool

    # --- Input Data ---
    corpus: list[dict] | None

    # Per-agent result payloads
    results: Annotated[dict[str, Any], operator.or_]
    report: dict[str, Any]
