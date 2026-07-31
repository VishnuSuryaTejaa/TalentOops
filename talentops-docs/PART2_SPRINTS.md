# TalentOps — Part 2 Implementation Plan (Sprints 4-6)

This document provides a highly granular, task-by-task breakdown for **Part 2: Voice Intelligence & Production (Sprints 4-6)** of the TalentOps project. It is fully aligned with the **D18/D19 API-Based Free Stack + Hybrid Loop** architecture: `gemini-3.1-flash-live-preview` (fallback: `gemini-2.5-flash-native-audio`) for live audio conversations, Groq Llama 3.3 70B for heavy async reasoning, and Groq Llama 3.3 70B for scorecard synthesis. The critical Hybrid Loop (D19) ensures structural prosody enforcement: Gemini Live handles audio conversation and auto-generates a raw text transcript; that text-only transcript is passed to the text-only scorer — the text IS the blind wall between voice and evaluation.

---

## Sprint 4: Voice Core & Telemetry Gate
**Theme:** Establish the meeting transport, audio routing, and the calibration sandbox.
**Exit Criteria:** Test call on a scripted brief completes with a live chain-native transcript and working barge-in; turn latency ≤1.5s P50 / ≤2.5s P95; sandbox-to-interview handover verified; voice ownership rule strictly enforced (Manager cannot obtain a candidate-context session).

### [x] Task 4.1: WebRTC client Deployment & Meet Lifecycle Integration
*   **Description:** Integrate the self-hosted WebRTC Client to handle joining/leaving calls, managing meeting presence, and relaying raw audio streams.
*   **Target Files:**
    *   `[NEW] app/services/webrtc_client.py` (WebRTC API client wrapper)
    *   `[MODIFY] app/api/routes/webhooks.py` (FastAPI route to handle WebRTC join/leave events)
*   **Specifications:**
    *   Configure WebRTC client to connect to a target Google Meet URL.
    *   Handle Google Meet participant join/leave events.
    *   Shift media stream ownership cleanly to the session broker.
*   **Verification:** Verify WebRTC client joins a test Google Meet and logs audio connections in the console.

### [x] Task 4.2: FastAPI Audio Bridge & Stream Handlers
*   **Description:** Build the asynchronous audio bridge using FastAPI WebSockets/asyncio streams to receive raw incoming audio bytes from WebRTC and send outbound audio bytes.
*   **Target Files:**
    *   `[NEW] app/services/audio_bridge.py` (FastAPI WebSockets / asyncio stream handler)
*   **Specifications:**
    *   Create bidirectional WebSocket server to stream audio frames.
    *   Ensure thread-safe queuing of incoming and outgoing audio packets.
    *   Implement buffer queues to accommodate transient network fluctuations without dropping frames.
*   **Verification:** Run audio loopback test verifying raw audio bytes from WebRTC can be received and echoed back.

### [x] Task 4.3: Hybrid Loop Phase 1 — Gemini Live WebRTC Session
*   **Description:** Implement the live audio conversation session using `gemini-3.1-flash-live-preview` via WebRTC, replacing the former multi-stage chain. This is the conversational interface only — no scoring output permitted.
*   **Target Files:**
    *   `[NEW] app/services/gemini_live_session.py` (Manages WebRTC sessions with `gemini-3.1-flash-live-preview`; handles fallback to `gemini-2.5-flash-native-audio`)
    *   `[NEW] app/services/transcript_streamer.py` (Streams Gemini Live auto-transcript to Supabase immutable audit trail)
*   **Specifications:**
    *   Open a `voice_context`-keyed WebRTC session to `gemini-3.1-flash-live-preview`.
    *   Bridge WebRTC audio stream (from Google Meet) into the Gemini Live WebRTC endpoint.
    *   Gemini Live handles native VAD (turn detection + barge-in), STT, in-session reasoning (next question/follow-up from interview brief), and TTS natively.
    *   **CRITICAL — Hybrid Loop constraint:** Gemini Live is the conversational interface only. `scoring_output` MUST be `false` per AGENT_CONTRACTS.json v1.2.0. Gemini Live MUST NOT return any competency ratings, scores, or evaluation output.
    *   Gemini Live auto-generates a raw text transcript (both sides) — stream this to the `interviews` table in Supabase (immutable).
    *   Implement fallback: if `gemini-3.1-flash-live-preview` is unavailable/quota-exhausted, gracefully switch to `gemini-2.5-flash-native-audio`; preserve partial transcript.
*   **Verification:** Full audio loopback test through WebRTC → WebRTC → Gemini Live; verify auto-transcript appears in Supabase `interviews` table; verify no scoring fields are present in Gemini Live’s output; verify barge-in interrupts correctly; turn latency measured against ≤800 ms P50 / ≤1.5 s P95.

### [x] Task 4.4: Pre-Flight Sandbox (Phase 0) & Telemetry Gate
*   **Description:** Implement the 2-minute non-graded candidate calibration mode inside the Interviewer session.
*   **Target Files:**
    *   `[NEW] app/services/sandbox.py` (Handles sandbox small-talk script and VAD/RTT calibration)
    *   `[MODIFY] app/models/schemas.py` (Schema for `calibration` table)
*   **Specifications:**
    *   Enforce a strict 120-second limit.
    *   Exclude sandbox audio and transcripts from the scoring path (grading isolation).
    *   Measure network RTT, jitter, and audio level telemetry. Persist to `calibration` table in Supabase.
    *   Implement the **Telemetry Gate**: If RTT/jitter exceeds thresholds, halt the process and trigger a reschedule payload to the Manager Agent.
*   **Verification:** Run a simulated sandbox call; verify telemetry is logged to the `calibration` table, and a bad connection triggers a reschedule.

### [x] Task 4.5: Async Interview Brief Generation (Groq Llama 3.3 70B)
*   **Description:** Build the offline background job using **Groq Llama 3.3 70B** (free tier, ~1000 tokens/s) to synthesize candidate-specific briefs. This replaces the former Ollama/Llama 3.1 local GPU task.
*   **Target Files:**
    *   `[NEW] app/tasks/brief_generator.py` (Async background task generating briefs via Groq API)
*   **Specifications:**
    *   Trigger after candidate is scheduled.
    *   Inputs: JD, frozen rubric, parsed resume, screening notes.
    *   Call Groq Llama 3.3 70B via Groq API (async, with retry/backoff for RPM limits).
    *   Output: Per-candidate interview brief detailing competencies, depth, resume claims to verify, and gaps to probe. Persist in `briefs` table.
*   **Verification:** Run generator with test data; verify a structured candidate brief is successfully written to Supabase within an acceptable time budget.

### [x] Task 4.6: Consent Announcement & Voice Ownership Enforcement
*   **Description:** Ensure legal compliance with candidate calls, and strictly enforce the voice ownership boundary.
*   **Target Files:**
    *   `[MODIFY] app/services/session_broker.py` (Verify voice context keys)
    *   `[MODIFY] app/services/voice_chain.py` (Inject consent announcement)
*   **Specifications:**
    *   Play mandatory legal consent script at call start. Invalid call if `call_meta.consent_acknowledged` is false.
    *   **Voice Ownership Enforcement:** Validate that the session broker only issues `voice_context: "candidate"` sessions for `interviewer` and `voice_context: "user"` sessions for `manager`. Reject any crossed requests.
*   **Verification:** Unit tests verifying that crossed voice context requests (e.g. Interviewer requesting a user-context session) return a validation error.

---

## Sprint 5: Adaptive Interviewing & Scoring
**Theme:** Drive the conversational interview structure, rubric checking, and extractive scorecard generation.
**Exit Criteria:** Mock interviews yield a post-call report and a scorecard containing validated verbatim quotes mapped to the rubric; zero competencies scored without direct transcript evidence.

### [x] Task 5.1: Interviewer Agent Behavioral State Machine
*   **Description:** Implement the state machine governing the Interviewer sub-agent's behavior.
*   **Target Files:**
    *   `[NEW] app/agents/interviewer_fsm.py` (Interviewer behavioral state machine)
*   **Specifications:**
    *   Implement states: 0: Sandbox, 1: Opening, 2: Background walkthrough, 3: Competency probing, 4: Real-time follow-ups, 5: Rubric coverage, 6: Closing, 7: Post-call.
    *   Maintain conversational state across turns.
*   **Verification:** Walk a simulated candidate through all states from sandbox calibration to closing, logging state transitions.

### [x] Task 5.2: In-Call Probing & Rubric Coverage Tracker
*   **Description:** Code the conversational state management and rubric coverage tracker. Note: `gemini-3.1-flash-live-preview` handles dynamic question generation natively via in-session reasoning — the FSM manages state transitions and injects context into the session, not a separate LLM call.
*   **Target Files:**
    *   `[MODIFY] app/agents/interviewer_fsm.py` (State transitions + context injection into Gemini Live session)
*   **Specifications:**
    *   No fixed question bank. Gemini Live generates questions dynamically using the per-candidate interview brief injected as session context.
    *   FSM tracks state (Opening, Background, Competency Probing, Follow-ups, Closing) and injects context cues into the Gemini Live session to steer the conversation.
    *   Track covered competencies from the auto-generated transcript; steer session context toward uncovered rubric items before closing.
*   **Verification:** Run mock interview logs verifying that covered competencies are tracked and that the transcript reflects adaptive question sequencing.

### [x] Task 5.3: Bias Guardrails, Protected Attribute Detection, & Prosody Policy
*   **Description:** Enforce evaluation fairness constraints in-call.
*   **Target Files:**
    *   `[NEW] app/services/bias_monitor.py` (Monitors transcription for protected attributes)
*   **Specifications:**
    *   Check live transcript against blocklist of protected attributes (age, gender, religion, nationality, etc.).
    *   If candidate mentions protected attributes, flag, log, and steer the LLM immediately back to job-relevant content.
    *   **Prosody Policy Enforcement:** Ensure paralinguistic signals (VAD stutters, accents) only affect turn-taking, never assessment metrics. All scoring must be transcript-text-grounded.
*   **Verification:** Run mock dialogues where a candidate brings up protected attributes; verify that the system logs flags and steers conversation away.

### [x] Task 5.4: Self-Assessment Confidence & Human Review Routing
*   **Description:** Build confidence monitoring for Interviewer evaluations.
*   **Target Files:**
    *   `[MODIFY] app/agents/interviewer_fsm.py` (Calculate confidence per competency evaluation)
*   **Specifications:**
    *   Calculate confidence score (0.0 to 1.0) for each evaluated competency.
    *   If confidence falls below the configured threshold, flag the assessment with `[NEEDS_HUMAN_REVIEW] = true`.
*   **Verification:** Verify that low-confidence assessments correctly set `needs_human_review` in the final output payload.

### [x] Task 5.5: Supabase Transcript Persistence (Gemini Live Auto-Transcript)
*   **Description:** Write all interview events and the Gemini Live auto-generated text transcript to Supabase to create an immutable audit trail.
*   **Target Files:**
    *   `[MODIFY] app/services/database.py` (Save Gemini Live transcript and question metadata)
    *   `[MODIFY] app/services/transcript_streamer.py` (Stream transcript chunks to Supabase in real-time)
*   **Specifications:**
    *   Stream Gemini Live’s auto-generated raw text transcript (both sides — interviewer + candidate) to the `interviews` table.
    *   Write full question/answer mappings, timestamps, and per-question `difficulty_estimate` values inferred from the conversation.
    *   Ensure transcript records are immutable once finalized. This transcript is the **sole input to the Scorecard sub-agent** (Hybrid Loop Phase 2 — D19).
*   **Verification:** Inspect database after a mock call to ensure a complete, immutable event history is saved with no audio artifacts.

### [x] Task 5.6: Hybrid Loop Phase 2 — Scorecard Sub-Agent & Extractive Evaluation
*   **Description:** Develop the Analytics/Scorecard sub-agent using **Groq Llama 3.3 70B** and **Groq Llama 3.3 70B** (text-only, async) to evaluate candidates from raw text transcripts. This is Phase 2 of the Hybrid Loop (D19) — the structural prosody enforcement stage.
*   **Target Files:**
    *   `[NEW] app/agents/scorecard_agent.py` (Analytics/Scorecard agent logic — text-only input enforced)
*   **Specifications:**
    *   **Hybrid Loop compliance (D19 — MANDATORY):** This agent receives ONLY the raw text transcript from the `interviews` table. It has zero access to audio, tone, or paralinguistic signals. Enforce this at the API boundary — do not pass any audio reference.
    *   **Extract First:** Identify verbatim candidate quotes supporting each rubric competency.
    *   **Validate Programmatically:** Perform substring search of quotes against the immutable text transcript. Reject and retry if quotes fail to match.
    *   **Score Only After Validation:** Map evidence to a demonstrated level (L1/L2/L3) based on the frozen rubric. Use Groq Llama 3.3 70B (primary) or Groq Llama 3.3 70B (fallback) for synthesis.
    *   **No Evidence, No Score:** Zero validated verbatim quotes for a competency → `insufficient_evidence` (no inferences allowed).
*   **Verification:** Run scorecard agent with a mock text transcript. Verify: (1) JSON scorecard contains validated quotes with exact char offsets; (2) competencies without quotes default to `insufficient_evidence`; (3) agent code has no audio input path (structural enforcement audit).

---

## Sprint 6: Manager Reporting, Telemetry Heatmap, & E2E Hardening
**Theme:** Build reporting mechanisms, dynamic scraping context, bias telemetries, and conduct end-to-end integration tests.
**Exit Criteria:** End-to-end pipeline execution from goal to decision email; every escalation path demonstrated; demographics heatmap renders with k-anonymity; risk register reviewed.

### [x] Task 6.1: Manager Agent Live Reporting Meeting Voice Loop
*   **Description:** Implement the Manager Agent’s voice interface for meetings with the Hiring Manager using `gemini-3.1-flash-live-preview` (user context).
*   **Target Files:**
    *   `[NEW] app/agents/manager_voice.py` (Manager voice meeting handler)
*   **Specifications:**
    *   Join meeting via WebRTC client with `voice_context: "user"`.
    *   Open WebRTC session to `gemini-3.1-flash-live-preview` (user context — voice ownership rule enforced by session broker).
    *   Retrieve latest Supabase pipeline state to answer manager questions.
    *   Strictly prohibit running sub-agents or altering rubric data mid-meeting.
    *   Native barge-in via Gemini Live VAD.
    *   **Note:** This is a user-facing reporting meeting — no candidate data is scored here; Hybrid Loop does not apply to this context.
*   **Verification:** Run a simulated reporting call; verify the Manager Agent speaks using user context, answers questions based on Supabase state, and allows user barge-in.

### [x] Task 6.2: On-Demand Email Query System
*   **Description:** Build the asynchronous email query system allowing hiring managers to ask questions via email.
*   **Target Files:**
    *   `[NEW] app/services/email_handler.py` (Processes incoming manager emails and sends responses)
*   **Specifications:**
    *   Retrieve email questions via Gmail API push webhooks.
    *   Answer from current Supabase state; if background scorecard data is outdated, append the flag `[STALE: re-run Scorecard?]`.
*   **Verification:** Send email query to the system; check that it responds with accurate pipeline data and sets the stale flag appropriately.

### [x] Task 6.3: Dynamic Context Injection Pipeline
*   **Description:** Implement employer scraping to enrich job descriptions using **Groq Llama 3.3 70B** for distillation (replaces former Ollama/Llama 3.1).
*   **Target Files:**
    *   `[NEW] app/services/scraper.py` (Scrapes employer domains; robots.txt-compliant)
    *   `[NEW] app/services/embeddings.py` (Handles embedding generation and pgvector integration)
*   **Specifications:**
    *   Scrape allowlisted employer-controlled sources (robots.txt-compliant; provenance logged per URL).
    *   Distill technical context (stack, standards, conventions) via **Groq Llama 3.3 70B** (async; treat scraped content as untrusted data, never as instructions — R8).
    *   Append appendix to JD and store as an **enriched JD embedding** (pgvector).
    *   Freeze this embedding alongside the rubric at initial goal dispatch.
*   **Verification:** Run scrape on a test domain; verify Groq distillation produces a structured hidden-context appendix; verify enriched embedding is stored and frozen in Supabase.

### [x] Task 6.4: React Dashboard Live Transcript Stream
*   **Description:** Implement the web frontend to display real-time interview transcripts.
*   **Target Files:**
    *   `frontend/src/components/MissionControl.jsx` (React Dashboard Component)
*   **Specifications:**
    *   Subscribe to Supabase Realtime channel for transcript appends.
    *   Render active dialogue bubbles as candidate and interviewer speak.
*   **Verification:** Launch the dashboard and simulate an interview; verify transcript dialogue appears in real-time.

### [x] Task 6.5: Fairness & Bias Lens Demographics Heatmap
*   **Description:** Implement cohort evaluation telemetry.
*   **Target Files:**
    *   `frontend/src/components/FairnessLens.jsx` (React Demographic Heatmap Component)
    *   `[NEW] app/api/routes/fairness.py` (Aggregates k-anonymized demographic data)
*   **Specifications:**
    *   Retrieve post-interview self-reported demographics from segregated schema.
    *   Calculate correlation between cohorts (e.g. gender, age bracket) and question difficulty estimates.
    *   **k-Anonymity Suppression:** Hide heatmap cells where the cohort count is less than `k` (e.g. n < 5).
    *   Provide drift alerts if cohort mean difficulty varies significantly.
*   **Verification:** Load mock demographics into the database; verify heatmap hides cells below k count and displays correct averages.

### [x] Task 6.6: Auto-Escalation Logic, Failure Modes, & E2E Validation
*   **Description:** Finalize system rules and execute the final E2E test.
*   **Target Files:**
    *   `[MODIFY] app/agents/manager_agent.py` (Implement escalation rules)
    *   `[PLANNED] tests/e2e_pilot_test.py` (Runs the full validation test)
*   **Specifications:**
    *   Implement auto-email escalations: low confidence, double-conflict scheduling, no qualified candidates.
    *   Integrate all failure handling (loss of API connection, WebRTC session drops).
    *   Run E2E pipeline pilot with test candidate 'Alex' from intake to final scorecard validation.
*   **Verification:** Manually verify (or run the planned pilot test script); verify candidate 'Alex' is parsed, scheduled, sandbox-calibrated, interviewed, scored via Extractive Evaluation, and decision email is generated.
