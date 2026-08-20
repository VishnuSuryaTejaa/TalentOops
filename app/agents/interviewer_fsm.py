"""Interviewer behavioral state machine (Tasks 5.1/5.2/5.4).

The FSM steers the Gemini Live session with context cues — it never generates a
fixed question bank and never scores (rating stays None; Hybrid Loop D19).
"""
import uuid
from datetime import datetime, timezone
from enum import IntEnum

from app.config import settings


from app.embeddings.embedder import get_embedder, cosine


class InterviewState(IntEnum):
    SANDBOX = 0
    OPENING = 1
    BACKGROUND = 2
    PROBING = 3
    FOLLOWUPS = 4
    RUBRIC_COVERAGE = 5
    CLOSING = 6
    POST_CALL = 7


CUES = {
    InterviewState.SANDBOX: "Open sandbox: initialize test interview environment.",
    InterviewState.OPENING: "Open warmly: intro, set context, put the candidate at ease.",
    InterviewState.BACKGROUND: "Background: Have the candidate walk through relevant experience; note claims to probe.",
    InterviewState.PROBING: "Probe brief competencies against their actual, specific usage.",
    InterviewState.FOLLOWUPS: "Follow up adaptively: Probe deeper on strong answers; vague -> ask how built.",
    InterviewState.RUBRIC_COVERAGE: "Probe rubric coverage to ensure all competency areas are evaluated.",
    InterviewState.CLOSING: "Closing: Invite candidate questions; note engagement.",
    InterviewState.POST_CALL: "Closing post-call: wrap up interview and log telemetry.",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InterviewerFSM:
    def __init__(self, rubric: dict, brief: dict, session,
                 confidence_threshold: float | None = None) -> None:
        self.rubric = rubric
        self.brief = brief
        self.session = session  # duck-typed: inject_context / next_turn
        self.threshold = (settings.CONFIDENCE_THRESHOLD
                          if confidence_threshold is None else confidence_threshold)
        self.state = InterviewState.SANDBOX
        self.transitions: list[InterviewState] = [self.state]
        self._answers: list[str] = []
        self._questions: list[dict] = []

    def advance(self) -> InterviewState:
        if self.state < InterviewState.POST_CALL:
            self.state = InterviewState(self.state + 1)
        else:
            self.state = InterviewState.SANDBOX
        self.transitions.append(self.state)
        return self.state

    def _competencies(self) -> list[dict]:
        return self.rubric.get("competencies", [])

    def _covered(self, comp: dict) -> bool:
        if not self._answers:
            return False
        blob = " ".join(self._answers).lower()
        terms = [comp.get("competency_id", "")] + list(comp.get("keywords", []))
        desc = comp.get("description", " ".join(terms))

        # Keyword matching
        kw_matched = any(t and t.lower() in blob for t in terms)
        if kw_matched:
            return True

        # Semantic embedding match
        try:
            embedder = get_embedder()
            blob_vec = embedder.embed(blob)
            comp_vec = embedder.embed(desc or " ".join(terms))
            sim = cosine(blob_vec, comp_vec)
            return sim >= 0.65
        except Exception:
            # Embedder unavailable (e.g. Groq has no embeddings endpoint)
            # Fall back to keyword-only result
            return False

    def _confidence(self, comp: dict) -> float:
        if not self._answers:
            return 0.0
        terms = [comp.get("competency_id", "")] + list(comp.get("keywords", []))
        desc = comp.get("description", " ".join(terms))

        hits, matched_len = 0, 0
        for a in self._answers:
            low = a.lower()
            if any(t and t.lower() in low for t in terms):
                hits += 1
                matched_len += len(a)

        kw_conf = min(1.0, 0.4 * hits + matched_len / 400.0)

        sim_scores = []
        try:
            embedder = get_embedder()
            comp_vec = embedder.embed(desc or " ".join(terms))
            for a in self._answers:
                if not a.strip():
                    continue
                a_vec = embedder.embed(a)
                sim_scores.append(cosine(a_vec, comp_vec))
        except Exception:
            # Embedder unavailable — return keyword-only confidence
            return kw_conf

        if sim_scores:
            max_sim = max(sim_scores)
            avg_sim = sum(sim_scores) / len(sim_scores)
            embed_conf = min(1.0, max(0.0, 0.7 * max_sim + 0.3 * avg_sim))
            return max(kw_conf, embed_conf)

        return kw_conf

    async def _turn(self, candidate_text: str, competency_id: str) -> None:
        cue = CUES.get(self.state)
        if self.state == InterviewState.PROBING:
            probes = self.brief.get("competencies_to_probe", [])
            uncovered_probes = [p for p in probes if not self._covered(p)]
            if uncovered_probes:
                cue = f"Probe remaining uncovered competencies: {', '.join(p.get('competency_id', '') for p in uncovered_probes)}"
            elif probes:
                cue = f"Probe: {', '.join(p.get('competency_id', '') for p in probes)}"
        if cue:
            await self.session.inject_context(cue)
        reply = await self.session.next_turn(candidate_text)
        self._answers.append(candidate_text)
        self._questions.append({
            "q_id": uuid.uuid4().hex, "ts": _now(), "competency_id": competency_id,
            "question_text": reply, "rating": None,  # interviewer NEVER scores (D19)
            "difficulty_estimate": min(3.0, 1.0 + len(candidate_text) / 200.0),
            "confidence": 0.0, "flags": [],
        })

    async def run_interview(self, candidate_turns: list[str],
                            transcript_ref: str = "") -> dict:
        started = _now()
        comps = self._competencies()
        turns = list(candidate_turns)
        total_turns = len(candidate_turns)
        base_share = max(1, total_turns // 4) if total_turns > 0 else 0

        # walk OPENING..FOLLOWUPS distributing candidate turns cleanly across states
        for st in (InterviewState.OPENING, InterviewState.BACKGROUND,
                   InterviewState.PROBING, InterviewState.FOLLOWUPS):
            self.advance()
            assert self.state == st
            turns_for_state = base_share if st != InterviewState.FOLLOWUPS else len(turns)
            for _ in range(turns_for_state):
                if not turns:
                    break
                comp_id = comps[len(self._questions) % len(comps)]["competency_id"] if comps else ""
                await self._turn(turns.pop(0), comp_id)
        self.advance()  # RUBRIC_COVERAGE
        uncovered = [c["competency_id"] for c in comps if not self._covered(c)]
        if uncovered:
            await self.session.inject_context(
                f"Before closing, steer naturally to uncovered competencies: {', '.join(uncovered)}")
        self.advance()  # CLOSING
        await self.session.inject_context(CUES[InterviewState.CLOSING])
        self.advance()  # POST_CALL

        confidences = {c["competency_id"]: self._confidence(c) for c in comps}
        for q in self._questions:
            q["confidence"] = confidences.get(q["competency_id"], 0.0)
        needs_review = any(v < self.threshold for v in confidences.values())
        return {
            "candidate_id": None,
            "transcript_ref": transcript_ref,
            "questions": self._questions,
            "anomaly_flags": [],
            "rubric_coverage": [{"competency_id": c["competency_id"],
                                 "covered": self._covered(c)} for c in comps],
            "needs_human_review": needs_review,
            "call_meta": {"started_ts": started, "ended_ts": _now(),
                          "consent_acknowledged": True,
                          "sandbox_telemetry_ref": None},
        }
