# TalentOps — Architecture Decision Records (ADR)

## ADR 001: Centralized LangGraph Supervisor with Upward-Only Subagent Communication

- **Status**: Accepted
- **Context**: TalentOps requires multi-agent orchestration for sourcing, screening, scheduling, interviewing, and evaluating candidates. Uncoordinated subagents communicating directly with HR cause disjointed reports, state corruption, and security boundary leaks.
- **Decision**: Adopt a centralized LangGraph `StateGraph` supervisor pattern (`app/graph/supervisor.py`). The **Manager Agent** acts as the central supervisor and sole liaison to Human HR. Subagents communicate exclusively upward to the Manager Agent via validated `Envelope` messages. Subagents are strictly forbidden from directly presenting results to Human HR.
- **Consequences**: Ensures zero reporting drift, single-source-of-truth workflow state management (`APPLICATION_RECEIVED` ➔ `SCREENING` ➔ `SCHEDULING` ➔ `INTERVIEWING` ➔ `EVALUATION` ➔ `HR_DEBRIEF`), and clean auditability.

---

## ADR 002: Frozen Rubric Standard Drift Protection via SHA-256 Hashing

- **Status**: Accepted
- **Context**: AI evaluation systems often suffer from "standard drift", where evaluation criteria change mid-hiring run or post-hoc, introducing unfair bias.
- **Decision**: Upon screening initiation, the screening subagent generates a weighted rubric from the hiring standard, canonicalizes its JSON representation, and computes a deterministic SHA-256 content hash (`rubric.content_hash`). Any attempt to alter rubric weights or competencies during evaluation raises an unrecoverable `RubricDriftError`.
- **Consequences**: Guarantees evaluation immutability across all candidates in a hiring run.

---

## ADR 003: Hexagonal Architecture (Ports & Adapters) for Audio Bridge & Storage

- **Status**: Accepted
- **Context**: The platform integrates with external services (WebRTC client, Gemini Live WebSocket Audio, Supabase pgvector, Google Drive API, Google Calendar API, SMTP Email). Direct coupling to external APIs creates fragile code and impedes automated testing.
- **Decision**: Implement Hexagonal Architecture (Ports & Adapters). Domain logic depends strictly on abstract interfaces (`Embedder`, `LLMClient`, `CalendarClient`, `WebRTCClient`, `DatabasePort`). Concrete infrastructure implementations adapt external APIs and can be swapped or mocked in unit tests without changing core domain code.
- **Consequences**: Decouples business logic from vendors, improves testability (119 test cases passing), and prevents vendor lock-in.

---

## ADR 004: Extractive Scorecards with Mandatory Verbatim Quotes

- **Status**: Accepted
- **Context**: Generative AI evaluators can hallucinate candidate statements or apply subjective bias when scoring candidate technical skills.
- **Decision**: The Candidate Evaluation Subagent evaluates candidate transcripts using strict extractive verification. Every competency score ($0.0 - 1.0$) must be paired with exact, verbatim transcript line quotes. Scores lacking verbatim quote evidence are flagged as `NEEDS_HUMAN_REVIEW`.
- **Consequences**: Eliminates AI hallucination in candidate scorecards and provides concrete audit evidence for Human HR.

---

## ADR 005: Demographic Cohort K-Anonymity Protection ($k \ge 5$)

- **Status**: Accepted
- **Context**: Fairness monitoring tools risk exposing PII or candidate identities when displaying question difficulty metrics across small demographic cohorts.
- **Decision**: The `/fairness/heatmap` service calculates cohort statistics only when the cohort sample size $n \ge 5$. For cohorts with $n < 5$, difficulty metrics are suppressed and marked as `INSUFFICIENT_DATA`.
- **Consequences**: Enforces compliance with privacy and data protection standards (GDPR/EEOC guidelines).
