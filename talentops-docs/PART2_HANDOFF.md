# TalentOps Part 2 — Handoff & Integration Guide

**Audience:** the Part 1 developer (Sprints 1–3: Manager Agent core, Sourcing/Screening, Scheduling, Communication) and anyone wiring the two halves together.
**Status:** Part 2 (Sprints 4–6) is partially complete — backend on `:8000`, dashboard on `:5173` (Note: Automated tests are currently WIP/manual).

---

## 1. What Part 2 is

Part 2 is the **Voice Intelligence & Production** half of TalentOps: everything from the moment a candidate joins a Google Meet until a decision email is drafted, plus the manager-facing reporting surfaces. It implements the **Hybrid Loop (D19)**: Gemini Live conducts the audio conversation and auto-generates a text transcript; scoring happens later, on that text only. The text transcript is the structural blind wall — no audio ever reaches the scorer.

### Module map (all paths relative to repo root)

| Area | File | What it does |
|---|---|---|
| Transport | `app/services/vexa_client.py` | Vexa bot join/leave/status for Google Meet |
| Transport | `app/api/routes/webhooks.py` | `POST /webhooks/vexa` lifecycle events → creates/tears down audio bridges |
| Transport | `app/services/audio_bridge.py` | Bounded async frame queues (drop-oldest), `WS /ws/audio/{meeting_id}` |
| Voice (Phase 1) | `app/services/gemini_live_session.py` | Gemini Live session (`gemini-3.1-flash-live-preview`, fallback `gemini-2.5-flash-native-audio`), barge-in, context injection, **no scoring surface** |
| Voice (Phase 1) | `app/services/transcript_streamer.py` | Streams both-side transcript chunks to the immutable audit trail |
| Pre-flight | `app/services/sandbox.py` | 120s non-graded calibration, telemetry gate → reschedule escalation |
| Pre-flight | `app/services/voice_chain.py` | Consent announcement; interaction blocked until acknowledged |
| Guardrail | `app/services/session_broker.py` | **Voice ownership rule**: only (`interviewer`,`candidate`) and (`manager`,`user`) sessions exist |
| Guardrail | `app/services/bias_monitor.py` | Protected-attribute detection + steering cue; `assert_no_prosody_inputs()` |
| Interview | `app/agents/interviewer_fsm.py` | 8-state behavioral FSM (Sandbox→Post-call), rubric coverage tracking, confidence → `needs_human_review`; never scores |
| Prep | `app/tasks/brief_generator.py` | Per-candidate brief via Groq Llama 3.3 70B (retry/backoff, rubric fallback) |
| Scoring (Phase 2) | `app/agents/scorecard_agent.py` | Extractive Evaluation: extract → substring-validate (char offsets) → score; `insufficient_evidence` when no validated quotes |
| Reporting | `app/agents/manager_voice.py` | Live reporting meeting (user context, read-only, refuses mutations) |
| Reporting | `app/services/email_handler.py` | Email Q&A from pipeline state; appends `[STALE: re-run Scorecard?]` |
| Context | `app/services/scraper.py` / `embeddings.py` | Allowlisted+robots-compliant scrape, Groq distillation (untrusted-data framing), frozen enriched-JD embedding |
| Fairness | `app/api/routes/fairness.py` | `GET /fairness/heatmap` — k-anonymized cohort × difficulty, drift alerts |
| Escalation | `app/agents/manager_agent.py` | Escalation rules (low_confidence, double_conflict, no_qualified_candidates, …) + `decide()` → invite/reject/hold |
| Dashboard | `frontend/src/components/TranscriptStream.jsx` | Live transcript stream (Supabase Realtime) |
| Dashboard | `frontend/src/components/FairnessHeatmap.jsx` | Demographics heatmap with suppression + drift banner |
| Shared | `app/config.py`, `app/services/database.py`, `app/models/schemas.py`, `app/services/llm_clients.py` | Settings, data layer, contract models (§4 of 04-API-EVENT-CONTRACT.md), Groq/OpenRouter clients |

### Run it

```bash
# backend (seeds demo data in offline mode)
/usr/local/bin/python3.11 -m uvicorn app.main:app --port 8000

# dashboard (proxies /fairness + /health to :8000)
npm --prefix frontend install && npm --prefix frontend run dev   # http://localhost:5173
```

**Offline vs live:** `settings.OFFLINE_MODE` is `True` unless **both** `GEMINI_API_KEY` and `SUPABASE_URL` are set. Offline, every external service (Supabase, Groq, OpenRouter, Gemini Live, Vexa, Gmail) is a deterministic in-process stub — that's what makes the whole pipeline testable with zero keys. Env vars for live mode: `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `VEXA_BASE_URL`.

---

## 2. What Part 2 expects from the Part 1 developer

Part 1 owns **goal intake → sourcing → screening → scheduling → outbound comms** (Sprints 1–3). Part 2 was built against the shared docs (01–04), so the expectations below are exactly the contract those docs define:

1. **Roles table with a frozen rubric.** At goal intake, persist `roles` rows shaped `{id, jd, difficulty_level: "L1|L2|L3", rubric: {difficulty_level, competencies: [{competency_id, keywords?}]}, frozen: true}`. The rubric must be immutable no later than the first Interviewer dispatch — every Part 2 component (brief, FSM coverage, scorecard) reads it as-is.
2. **Candidates table.** Sourcing/Screening writes `candidates` rows `{id, role_id, name, resume, screening_notes?}` plus similarity scores. `brief_generator.on_candidate_scheduled()` pulls `roles` + `candidates` by id — keep those field names.
3. **A scheduling completion event.** When a slot is confirmed, emit the `scheduling` → `task.result` envelope (04 §4.3) and call (or trigger) `app.tasks.brief_generator.on_candidate_scheduled({"role_id", "candidate_id"})`. The invite must include the 2-minute Pre-Flight Sandbox window.
4. **The Manager Agent supervisor (LangGraph).** Part 2 ships `ManagerAgent` with escalation rules and `decide()`, but Part 1 owns the supervisor graph that sequences sub-agents. Slot Part 2's pieces in as graph nodes (see §3 call order) rather than re-implementing them.
5. **Communication sub-agent.** Part 2's `email_handler.send_email()` writes to the `comms` log (offline) — Part 1's Gmail API integration should replace/extend that send path. Offer emails require explicit user approval (PRD §1.4); `ManagerAgent.decide()` only ever returns `invite | reject | hold` — it never sends offers.
6. **Message envelopes.** All cross-agent messages must validate against `app/models/schemas.py::Envelope`. Voice-context validation is enforced there (crossed contexts raise) — don't bypass it.
7. **Real Supabase schema.** The offline store mimics tables: `roles, enriched_jd, candidates, briefs, scheduling, calibration, interviews, scorecards, demographics, comms, events` (+ transcript chunks). Part 1's Supabase migration should create these; `app/services/database.py` already delegates to supabase-py when live. `demographics` must be a segregated schema with RLS denying all agent roles — the fairness route only aggregates.

---

## 3. How to connect Part 1 ↔ Part 2

### Pipeline call order (what the supervisor graph invokes, in sequence)

```python
# 0. goal intake (Part 1): insert roles row, freeze rubric
# 1. context injection (pre-sourcing):
pages    = await scraper.scrape_employer(domain, allowlist=[...])
appendix = await scraper.distill_hidden_context(pages)
await embeddings.store_enriched_jd(role_id, jd, appendix)   # frozen — 2nd call raises

# 2. sourcing/screening + shortlist + scheduling (Part 1) → on confirmation:
brief_row = await brief_generator.on_candidate_scheduled({"role_id": ..., "candidate_id": ...})

# 3. candidate call (Part 2 owns everything inside the call):
session = broker.issue_session("interviewer", "candidate")   # raises on crossed context
chain   = VoiceChain(session); await chain.open_call(); chain.acknowledge_consent()
sandbox = await PreFlightSandbox(session, interview_id).run(telemetry)
#    -> if sandbox["passed"] is False: ManagerAgent.escalate(**sandbox["escalation"]) and STOP
live    = GeminiLiveSession(session, interview_id, brief=brief_row["brief"]); await live.start()
result  = await InterviewerFSM(rubric, brief_row["brief"], live).run_interview(turns)
await db.insert("interviews", {"id": interview_id, "role_id": ..., "candidate_id": ..., **result})
await db.finalize_transcript(interview_id)                   # immutable from here

# 4. async scoring (Hybrid Loop Phase 2 — text only):
scorecard = await ScorecardAgent().score(interview_id, rubric, candidate_id)

# 5. decision + comms (Part 1's Communication agent sends what decide() drafts):
decision = await ManagerAgent(role_id).decide(scorecard)     # invite | reject | hold
```

### HTTP/WS surface Part 1 can rely on

- `GET /health` — liveness
- `POST /webhooks/vexa` — point the Vexa deployment's webhook here
- `WS /ws/audio/{meeting_id}` — audio frame bridge
- `GET /fairness/heatmap?role_id=&k=` — dashboard telemetry (aggregate-only)

### Invariants Part 1 must never break

1. **Voice ownership:** never request a session outside (`interviewer`,`candidate`)/(`manager`,`user`) — the broker and the Envelope validator will both reject it. The Manager Agent must never obtain a candidate-context session, even for "quick checks".
2. **Hybrid Loop:** never pass audio (or anything derived from it) to `ScorecardAgent` — its only input is `interview_id` + rubric; it reads the text transcript itself. `assert_no_prosody_inputs()` is available for defense-in-depth on any scoring payload.
3. **Immutability:** never update `interviews` transcripts after `finalize_transcript()` (raises `TranscriptFinalizedError`), never rewrite the frozen rubric or enriched JD (raises `RuntimeError`).
4. **Sandbox isolation:** sandbox dialogue must never be written to the interview transcript or reach scoring — only `calibration` telemetry persists.
5. **Consent:** a candidate-call `task.result` is valid only with `call_meta.consent_acknowledged = true` (04 §preamble); `VoiceChain` enforces it in-call.

### Suggested joint milestone

(Planned) Run `tests/e2e_pilot_test.py` (candidate "Alex") once the test suite is implemented. Every table assertion in that test will double as the integration checklist: `roles, enriched_jd, candidates, briefs, scheduling, calibration, interviews, scorecards, comms, events` all populated, every evidence quote offset-validated against the immutable transcript.

---

## 4. Known gaps / deliberate stubs (for the joint backlog)

- Real WebRTC bridging Vexa ⇄ Gemini Live (current `GeminiLiveSession` simulates turns offline; the online path is scaffolded, not wired).
- Gmail push webhooks for `email_handler` (currently a direct async call + comms log).
- LangGraph checkpointing to Supabase (Part 1's supervisor state).
- Turn-latency measurement harness (S4 exit criterion: ≤800 ms P50 / ≤1.5 s P95) — needs the live stack.
- k threshold and confidence/drift thresholds are configurable defaults (`app/config.py`) pending pilot baselining ([TBD]s in the docs).
