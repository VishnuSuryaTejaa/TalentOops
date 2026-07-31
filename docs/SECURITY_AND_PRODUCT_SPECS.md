# TalentOps — Security Review & Product Acceptance Criteria

## 1. Security Review & Vulnerability Audit

### 1.1 Audio Streaming & WebSocket Defense
- **Meeting ID Validation**: WebSocket route `@app.websocket("/ws/audio/{meeting_id}")` validates meeting ID format and requires token validation to prevent unauthorized audio eavesdropping.
- **Resource Limits**: Configures binary audio frame length limits ($< 64 \text{ KB}$ per message frame) to prevent memory exhaustion / DoS attacks.

### 1.2 Credential & Token Security
- **OAuth Token Storage**: `token.json` (Google Drive & Calendar OAuth) is strictly excluded from version control via `.gitignore`.
- **Environment Secrets**: Database keys (`SUPABASE_KEY`), LLM API keys (`GROQ_API_KEY4`, `GROQ_API_KEY`), and SMTP credentials (`SMTP_PASSWORD`) are loaded strictly from environment variables via Pydantic `Settings`. No hardcoded secrets exist in source code.

### 1.3 Data Protection & PII Defense
- **Subagent Reporting Boundary**: Raw PII (candidate phone numbers, personal emails, residential addresses) extracted during sourcing is isolated inside subagent state and never exposed via public endpoints.
- **K-Anonymity Guard ($k \ge 5$)**: The `/fairness/heatmap` API suppresses cohort difficulty scores when cohort sample size $n < 5$, preventing identity leakage.
- **SQL Injection Defense**: Supabase client uses parameterized REST / PostgREST queries and RPC function calls, preventing raw string SQL concatenation vulnerabilities.
- **XSS Prevention**: React frontend renders all transcript lines and report summaries using standard text JSX bindings, escaping HTML entities automatically.

---

## 2. Product Acceptance Criteria per Subagent

### 2.1 Manager Agent (Supervisor & Human HR Liaison)
- [x] Must act as the **sole point of contact** for Human HR.
- [x] Must transition pipeline state through explicit workflow stages: `APPLICATION_RECEIVED` $\rightarrow$ `SCREENING` $\rightarrow$ `SCHEDULING` $\rightarrow$ `INTERVIEWING` $\rightarrow$ `EVALUATION` $\rightarrow$ `HR_DEBRIEF`.
- [x] Must present candidate evaluation reports verbally in a dedicated Manager Debrief Google Meet session.

### 2.2 Resume Screening Subagent
- [x] Must ingest PDF/Docx resumes from Google Drive folder URLs or local uploads.
- [x] Must match candidate profile vectors against a frozen rubric content hash ($\text{SHA-256}$).
- [x] Must send candidate rankings **ONLY** upward to the Manager Agent via Envelope.

### 2.3 Scheduling & GMeet Subagent
- [x] Must query Google Calendar `FreeBusy` API to locate open 45-minute slots.
- [x] Must create Google Meet rooms and dispatch formatted invitation emails to candidates via SMTP/Gmail.
- [x] Must report booking metadata **ONLY** upward to the Manager Agent.

### 2.4 Interviewer Subagent (Candidate-Facing)
- [x] Must deploy WebRTC client into candidate Google Meet calls.
- [x] Must execute the 8-stage Interviewer FSM over bi-directional PCM audio WebSockets.
- [x] Must log verbatim audio transcript lines and send raw logs **ONLY** to the Manager Agent.

### 2.5 Candidate Evaluation Subagent
- [x] Must score candidate competencies backed strictly by exact verbatim transcript quotes.
- [x] Must flag items lacking verbatim quote matches with `needs_review=True`.
- [x] Must submit structured scorecards **ONLY** to the Manager Agent.
