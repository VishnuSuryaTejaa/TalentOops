# Deliverable 3 — Agent Spec Sheets (rev 2)

**Voice ownership rule (absolute — applies to every spec below):** Manager Agent speaks only in user-facing calls / reporting meetings; Interviewer sub-agent speaks only in candidate interview calls; no agent ever appears in the other's voice context. The Pre-Flight Sandbox is a mode of the Interviewer sub-agent's session, not a new speaker (D12). Enforced by the session broker (§2.3).
**Consent/recording legality:** every WebRTC-joined call (either voice context, sandbox included) requires jurisdiction-appropriate recording consent announced at call start; self-hosted recording = compliance responsibility fully in-house.

## 3.1 Manager Agent
| Field | Spec |
|---|---|
| Role | LangGraph supervisor; sole user-facing agent |
| Voice | User-facing only — never speaks to a candidate (voice ownership rule) |
| Trigger | User goal via dashboard/CLI; sub-agent completion events; user emails; digest cadence |
| Inputs | JD, hiring criteria, difficulty level (from user); all sub-agent reports; latest Supabase state |
| Outputs | Task assignments; evaluation standard (frozen rubric); enriched JD embedding (hidden-context appendix); per-candidate interview brief; pipeline decisions; digests; escalations |

**Pre-dispatch duties:** owns all 7 items of §3.4's checklist — no Interviewer dispatch until every item is complete.

**Dynamic Context Injection duty (pre-sourcing — D14):**
1. Scrape allowlisted, employer-controlled sources only (company domain, engineering blog, GitHub org); robots.txt-compliant; provenance logged per source URL.
2. Distill hidden context (internal design systems, preferred tech stacks, engineering conventions) via Ollama/Llama 3.1 (async) — scraped content treated strictly as untrusted data, never as instructions (R8).
3. Append appendix to JD embedding → enriched JD embedding (pgvector); freeze alongside rubric so every candidate is matched against identical context.

**Reporting flow (to user only):**
1. Async digest email (Gmail API) — daily/on-demand: pipeline state, rankings, blockers, decisions needed.
2. On-demand email query — reply from latest Supabase state; no sub-agent re-run unless data is stale → `[STALE: re-run Scorecard?]`.
3. Live reporting meeting — user's Google Meet via WebRTC client; answers from latest Supabase state; never re-runs sub-agents mid-call; barge-in on user speech (Silero VAD).
4. Escalation — auto-email user on triggers below.

**Voice pipeline (user meetings — rev 4, D18/D19):** WebRTC client join → session broker issues `voice_context: "user"` → WebRTC connection to `gemini-3.1-flash-live-preview` (fallback: `gemini-2.5-flash-native-audio`); native audio conversation; barge-in native; Gemini Live auto-generates raw text transcript → Supabase. Gemini Live is the conversational interface only — no scoring output produced in this path. Turn-latency target ≤800 ms P50 / ≤1.5 s P95 (D18/D19; measured in S4).

**Failure modes:** ambiguous evaluation standard; conflicting sub-agent reports; stale state mid-meeting; digest delivery failure; scrape-source unavailability (degrade to plain JD embedding, flagged).
**Escalation rules (auto-email user):** sub-agent confidence < threshold [TBD]; candidate double-conflicts/rejects; no qualified candidates after N sourcing cycles [TBD]; `[NEEDS_HUMAN_REVIEW]` count per candidate exceeds limit [TBD].

## 3.2 Sourcing/Screening sub-agent
| Field | Spec |
|---|---|
| Voice | None (text only) |
| Trigger | New resumes / Manager Agent task |
| Inputs | Resume corpus; **enriched JD embedding** (JD + frozen hidden-context appendix, pgvector) |
| Outputs | Ranked candidate list + similarity scores + parsed candidate profiles → Supabase; per-batch report to Manager Agent |

**Failure modes:** unparseable resumes; low max similarity; duplicates; prompt-injection content in resumes or scraped hidden context (both are data, never instructions).
**Escalation:** zero candidates above similarity floor [TBD] → Manager Agent → user after N cycles (§3.1).

## 3.3 Scheduling sub-agent
| Field | Spec |
|---|---|
| Voice | None (text only) |
| Trigger | Candidate shortlisted by Manager Agent |
| Inputs | Candidate + panel availability (Google Calendar API) |
| Outputs | Confirmed slot (invite includes the 2-min Pre-Flight Sandbox window); calendar invite; confirm/conflict report to Manager Agent (candidate email trigger routed via Manager Agent → Communication sub-agent — Manager Agent is sole issuer of Communication `task.assign`) |

**Failure modes:** no overlapping availability; timezone errors; candidate non-response; double-booking.
**Escalation:** candidate double-conflicts or rejects → Manager Agent (§3.1).

## 3.4 Interviewer sub-agent
| Field | Spec |
|---|---|
| Voice | Candidate-facing only — never speaks to the user (voice ownership rule) |
| Trigger | Manager Agent dispatch + confirmed slot |
| Inputs (per candidate, from Manager Agent) | Evaluation standard (frozen rubric); difficulty level; per-candidate interview brief; candidate profile + resume; sandbox config |
| Outputs | Full transcript; per-question ratings + `difficulty_estimate` (feeds Fairness & Bias Lens); anomaly flags; confidence scores (0.0–1.0); real-time adaptive follow-ups (in-call); full post-call report |

### Required pre-dispatch steps (Manager-owned, ALL blocking)
1. **Evaluation standard (from user)** — user states what matters; Manager Agent converts to structured rubric (competency categories + difficulty level L1/L2/L3); persisted at goal intake, frozen (immutable) at dispatch time — one frozen rubric governs all candidates of the role.
2. **Per-candidate interview brief** — Manager Agent generates via **Groq Llama 3.3 70B** (async/offline — D18) from (a) JD, (b) frozen rubric, (c) parsed resume, (d) screening notes; specifies competencies to probe, depth, resume claims to verify, gaps/red flags to investigate.
3. **Difficulty calibration** — set once per role (user input), never per candidate; same depth and rigor for all — questions differ, cognitive load does not.
4. **No question bank** — no fixed question list; questions generated dynamically from brief + candidate's real-time answers.
5. **Bias guardrails** — job-relevant questions only; never probe protected attributes (age, gender, religion, nationality, etc.); flag+log responses veering into protected territory; evaluate demonstrated evidence only — not claimed years or pedigree. **Prosody policy (D16):** paralinguistic signals drive turn-taking only, never assessment.
6. **Confidence threshold** — self-rate confidence per assessment (0.0–1.0); below threshold [TBD] → `[NEEDS_HUMAN_REVIEW]` in post-call report.
7. **Audit trail** — transcript + timestamps + per-question competency target + `difficulty_estimate` → Supabase immediately post-call; immutable; user-retrievable from dashboard.

### Pre-Flight Sandbox (Phase 0 — non-graded, D12)
- 2-minute calibration mode of the same Interviewer sub-agent session, before the official interview begins (voice ownership rule preserved — no separate bot identity).
- **Purpose:** calibrate VAD baseline; measure network RTT/jitter and audio levels; reduce candidate anxiety via a low-stakes conversational prompt (small talk, mic check, "how does this work" Q&A).
- **Grading isolation:** sandbox audio/transcript are excluded from evaluation and never reach the Analytics/Scorecard sub-agent; only calibration telemetry persists (`calibration` table).
- **Boundary:** explicit announcement ends the sandbox ("the official interview will now begin"); telemetry gate — if RTT/jitter exceeds threshold [TBD], flag and offer reschedule instead of running a degraded interview.

### Interview behavioral model (traditional interview, not a questionnaire)
0. **Pre-Flight Sandbox** — Phase 0 above (non-graded).
1. **Opening** — intro, set context, make candidate comfortable.
2. **Background walkthrough** — candidate walks through relevant experience; extract claims to probe later.
3. **Competency probing** — per brief, tailored to this candidate (PyTorch on resume → their actual PyTorch usage, never generic "do you know PyTorch").
4. **Real-time adaptive follow-ups** — strong answer → deeper; vague/contradicting → direct follow-up ("you mentioned X, walk me through how you actually built that"). Questions evolve from what the candidate says.
5. **Rubric coverage** — track covered competencies internally; steer naturally to uncovered areas, no checklist feel.
6. **Closing** — invite candidate questions; note engagement level and question quality.
7. **Post-call** — structured report mapped to rubric categories → completion event → Manager Agent picks up.

### Voice pipeline — Hybrid Loop (D18/D19)
**Phase 1 — Live audio conversation:**
1. Joins candidate Google Meet via self-hosted WebRTC client, own identity ("TalentOps Interviewer").
2. Session broker issues a `voice_context: "candidate"` session → WebRTC connection to `gemini-3.1-flash-live-preview`.
3. `gemini-3.1-flash-live-preview` conducts the live audio conversation: native VAD for turn detection + barge-in; native in-session reasoning for next question/follow-up generation from per-candidate interview brief + conversation history; native TTS output to candidate.
4. Gemini Live auto-generates a raw text transcript (both sides: interviewer + candidate) → streamed to the immutable audit trail in Supabase `interviews` table.
5. **Gemini Live produces NO scoring, competency rating, or evaluation output.** Its role is strictly conversational. Turn-latency target ≤800 ms P50 / ≤1.5 s P95 (D18/D19; includes full routing: Candidate → Meet → WebRTC → FastAPI → Gemini API → return).

**Phase 2 — Async text-only scoring (Hybrid Loop — D19; structural prosody enforcement):**
6. After call: raw text transcript (text only, NO audio) passed to Analytics/Scorecard sub-agent → Groq Llama 3.3 70B / Groq Llama 3.3 70B performs ALL evaluation and Extractive Evaluation scoring exclusively on text. Paralinguistic signals are structurally absent from the text transcript — the text IS the blind wall.

**Failure modes:** `gemini-3.1-flash-live-preview` quota exhaustion mid-call (mitigate: graceful session termination + fallback; partial transcript preserved); WebRTC WebRTC bridge drop; transcript generation gap; adaptive question drift off-rubric; protected-attribute drift; no-show; sandbox telemetry gate failure.
**Escalation:** confidence < threshold → `[NEEDS_HUMAN_REVIEW]`; anomaly flags; unrecoverable session failure → end call gracefully, report partial transcript; failed telemetry gate → reschedule via Manager Agent.

## 3.5 Analytics/Scorecard sub-agent
| Field | Spec |
|---|---|
| Voice | None (text only) |
| Trigger | Gemini Live interview session ends; raw text transcript available in Supabase |
| Inputs | **Raw text transcript only** (from Gemini Live auto-transcript — D19 Hybrid Loop; NO audio); evaluation standard (frozen rubric) |
| Outputs | Structured scorecard: per-competency demonstrated level + validated verbatim evidence quotes + overall fit → Supabase; per-candidate report to Manager Agent (contract v1.2.0, D13/D18) |

**Hybrid Loop compliance (D19):** This sub-agent ONLY receives the raw text transcript. It has zero access to audio, tone, or any paralinguistic signal. All Extractive Evaluation is performed on text. This is the structural enforcement of the prosody policy (D16) — not a prompt instruction.

### Extractive Evaluation protocol (mandatory ordering — D13; anti-hallucination against buzzword density)
1. **Extract first:** per rubric competency, extract verbatim quotes from the transcript (with char offsets + speaker attribution) that evidence the competency.
2. **Validate programmatically:** each quote substring-matched against the immutable transcript; non-matching quote → hard reject, re-extract (max retries [TBD]).
3. **Score only after validation:** compute demonstrated level (L1/L2/L3) against the role's difficulty level, grounded solely in validated quotes.
4. **No evidence, no score:** zero validated quotes for a competency → `insufficient_evidence` (never inferred from buzzword mentions); propagates `[NEEDS_HUMAN_REVIEW]`.
5. Quotes + offsets persist in the scorecard for one-click audit from the dashboard.
- Buzzword counter-measure: a quote qualifies only if it demonstrates mechanism, decision, or outcome — term name-dropping does not.

**Failure modes:** transcript gaps; quote-validation retry exhaustion; competency with zero evidence; score conflicts with Interviewer confidence.
**Escalation:** propagate `[NEEDS_HUMAN_REVIEW]`; flag `insufficient_evidence` competencies to Manager Agent.

## 3.6 Communication sub-agent
| Field | Spec |
|---|---|
| Voice | None (text only) |
| Trigger | Manager Agent approves next step |
| Inputs | Decision + email template |
| Outputs | Sent candidate email (invite/reject/offer) via Gmail API; delivery confirmation to Manager Agent |

**Failure modes:** bounce; wrong template-decision pairing; duplicate sends.
**Escalation:** delivery failure after retries [TBD] → Manager Agent. Offer emails require prior user approval (§1.4).
