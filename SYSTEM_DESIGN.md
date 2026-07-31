# TalentOps — Complete System Design Details

## 1. System Vision & Architecture Principles

TalentOps is designed around **five fundamental software engineering principles**:

1. **Standard Drift = 0 (Goal G2)**: Evaluates candidates strictly against a frozen rubric content hash ($\text{SHA-256}$). No post-hoc standard modification is allowed.
2. **Voice Ownership Rule (Goal G4)**: All candidate-facing and user-facing communications are exclusively owned and dispatched by the Manager Agent to prevent disjointed multi-agent channels.
3. **Verbatim Evidence Scorecard (Goal G3)**: Every score assigned to a candidate must be backed by exact verbatim transcript quotes.
4. **Demographic K-Anonymity Guard (Goal G6)**: Demographic cohort metrics require $k \ge 5$ candidate samples per cell; otherwise data is suppressed to protect candidate anonymity.
5. **Human Escalation Gate (Goal G5)**: Any evaluation step yielding confidence $< 0.6$ emits a `NEEDS_HUMAN_REVIEW` audit flag for human-in-the-loop review.

---

## 2. End-to-End Execution Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as Hiring Manager
    participant UI as React Frontend
    participant API as FastAPI Backend
    participant Supabase as Supabase DB (pgvector)
    participant Supervisor as LangGraph Supervisor
    participant SubAgents as Sub-Agents (Sourcing/Screening/Scheduling)
    participant WebRTC as WebRTC Client
    participant Gemini as Gemini Live Audio Engine
    participant Evaluator as Evaluator Agent

    User->>UI: Input Goal, Standard & Drive Link
    UI->>API: POST /run
    API->>Supervisor: run_pipeline(goal, standard, corpus)
    
    Supervisor->>SubAgents: Sourcing Node (Fetch Drive PDFs)
    SubAgents->>Supabase: Store Candidate Embeddings (pgvector)
    
    Supervisor->>SubAgents: Screening Node (Freeze Rubric SHA-256)
    SubAgents->>Supabase: match_embeddings RPC
    
    Supervisor->>SubAgents: Scheduling Node (Google Calendar)
    SubAgents-->>User: Dispatch Candidate Invite Email (SMTP)
    
    Supervisor->>SubAgents: Interviewer Node
    SubAgents->>WebRTC: Deploy Bot to Candidate Meet URL
    WebRTC<->>Gemini: Bi-directional Audio Stream (/ws/audio)
    
    Supervisor->>SubAgents: Reporting Node
    SubAgents->>Evaluator: Evaluate Transcript & Verbatim Quotes
    
    SubAgents->>WebRTC: Deploy Manager AI Bot to User Meet Link
    Supervisor-->>API: Return Pipeline Result & Manager Debrief Link
    API-->>UI: Display Visualizer, Scorecard, Heatmap & Join Debrief Button
    User->>WebRTC: Join Manager Debrief Google Meet Call
```

---

## 3. Detailed Stage-by-Stage Lifecycle

### Stage 1: Goal Ingestion & Rubric Freezing
- User inputs a hiring goal (e.g. *"Hire a Senior Backend Engineer"*) and an evaluation standard.
- `generate_rubric()` calls the LLM to derive weighted competencies ($\sum w_i = 1.0$).
- Canonical JSON is hashed via SHA-256 into `rubric.content_hash`.
- The rubric record is persisted in Supabase `rubrics`.

### Stage 2 & 3: Sourcing and Screening (Combined in `sourcing_node`)
- Sourcing agent accepts local PDF paths or Google Drive URLs (`https://drive.google.com/drive/folders/...`).
- `fetch_resumes_from_drive()` lists and downloads PDF files, extracting candidate names and emails.
- Text is embedded via `RemoteEmbedder` (384-dimensional unit vector) and upserted into `embeddings`.
- The hiring goal text is embedded into a query vector $Q$.
- Executes Supabase RPC `match_embeddings(p_run_id, 'candidate', Q, top_k=3)` using cosine distance ($1 - (E \cdot Q)$).
- Computes rubric competency coverage fraction per candidate.
- Applies confidence gate: $\text{confidence} = 0.5 \times \text{similarity} + 0.5 \times \text{coverage\_rate}$.

### Stage 4: Scheduling & Candidate Email Invite
- Queries Google Calendar `FreeBusy` API for available 45-minute slots.
- Creates a Google Calendar event containing a live Google Meet room URL.
- Manager Agent calls `send_invite()`, dispatching an email with the Meet link and time to the candidate's real email address.

### Stage 4.5: WAITING_FOR_INTERVIEW
- System pauses and awaits the scheduled interview time.

### Stage 5: Live Multimodal Audio Interview
- At the scheduled time, `WebRTCClient.join_meeting()` deploys a headless Meet bot.
- Audio frames stream bi-directionally over WebSocket `@app.websocket("/ws/audio/{meeting_id}")`.
- `InterviewerFSM` transitions through the 8-stage interview lifecycle, injecting prompt context per stage.

### Stage 6 & 7: Extractive Scorecard & Fairness (Bundled in `reporting_node`)
- `EvaluatorAgent.evaluate_transcript()` evaluates the complete interview transcript.
- Requires exact verbatim candidate quotes for each scored competency score ($0.0 - 1.0$).
- Output scorecard is written to Supabase `scorecards`.
- `/fairness/heatmap` computes question difficulty across candidate cohorts (gender, ethnicity, experience level).
- Applies $k$-anonymity suppression: if cohort sample size $n < 5$, cell difficulty values are hidden to prevent identification.

### Stage 8: Manager AI Debriefing Session
- `create_manager_debrief_session()` generates a dedicated **Manager Debrief Google Meet link**.
- Deploys a WebRTC client with `voice_context="manager_debrief"`.
- When the hiring manager joins the call, the AI Manager Agent verbally briefs them on Drive resumes processed, candidate screening scores, verbatim quotes, and final hiring recommendations (`ADVANCE` / `REJECT` / `HOLD`).

---

## 4. Configuration & Environment Matrix (`.env`)

```env
# Server Configuration
CORS_ORIGINS=http://localhost:5173
LOG_LEVEL=INFO
IS_PRODUCTION=false

# Supabase Vector Store
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-key

# AI LLM & Embedding Services
LLM_PROVIDER=groq
LLM_MODEL=meta-llama/llama-3.3-70b-instruct
GROQ_API_KEY4=sk-or-v1-your-groq-key
EMBED_PROVIDER=groq
EMBED_DIM=384

# Candidate Email SMTP Gateway
EMAIL_PROVIDER=smtp
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_USE_TLS=true

# Google Calendar API Integration
CALENDAR_PROVIDER=google
GOOGLE_TOKEN_PATH=token.json

# WebRTC Client Client
WEBRTC_API_BASE=http://localhost:18056
WEBRTC_API_KEY=your-webrtc-api-key
```

---

## 5. Verification & Test Suite Strategy

Currently, the test suite is **[Planned / WIP]**. The automated unit and integration tests originally planned for `app/tests/` and `talentops-part1/tests/` have not been implemented in the codebase.
Testing is currently performed manually by running the backend API and frontend React application.
