# PROJECT_CONTEXT.md — canonical summary (rev 2). Paste FIRST into every Antigravity session.

**System:** TalentOps — Manager Agent (LangGraph supervisor) + 5 sub-agents running recruitment pipelines: sourcing → screening → scheduling → interviewing → reporting.

**Stack (mono-stack Pure Python — D10; API-based free tier — D18/D19):** LangGraph (supervisor) · FastAPI monolith (async webhooks, Gemini Live session manager, `asyncio` background tasks — no Node/Celery/Redis) · React/Vite (dashboard incl. Fairness & Bias Lens) · Supabase+pgvector · **Gemini Live API** (`gemini-3.1-flash-live-preview`, fallback: `gemini-2.5-flash-native-audio`; native audio-in/audio-out via WebRTC — D18/D19; conversational interface only — no scoring output permitted) · **Hybrid Loop (D19):** Gemini Live auto-generates raw text transcript → fed async to Groq/Nemotron for ALL evaluation (text transcript IS the structural wall between voice and scorer, replacing D17’s STT boundary) · **Groq Free Tier** (Llama 3.3 70B — heavy reasoning async/offline: rubrics, briefs, hidden-context distillation, Extractive Evaluation scoring) · **OpenRouter Free Tier** (NVIDIA Nemotron — complex scorecard synthesis, fallback to Groq Llama 3.3 70B) · Gmail API · Google Calendar API · **WebRTC** (self-hosted OSS Google Meet bot — meeting transport + WebRTC audio bridging to Gemini Live). Eliminated: Recall.ai, GPT-4o Realtime, ElevenLabs (D17); Silero VAD, Groq Whisper STT, self-hosted Kokoro TTS, locally hosted Ollama/Llama 3.1 (D18). Turn-latency target: ≤800 ms P50 / ≤1.5 s P95 (D18/D19; single-hop WebRTC; accounts for Candidate → Meet → WebRTC → FastAPI → Gemini routing; measured in S4). Hosted APIs: Gemini Live API (voice) · Groq free tier (fast text reasoning) · OpenRouter free tier (Nemotron scorecard).

**Voice ownership rule (ABSOLUTE — never cross, never reinterpret):**
| Voice context | Speaks | Listens |
|---|---|---|
| User-facing calls / reporting meetings | Manager Agent only | User |
| Candidate interview calls | Interviewer sub-agent only | Candidate |
Manager never speaks to a candidate. Interviewer never speaks to the user. Enforced by the session broker (voice-chain sessions keyed by `voice_context`) + message validation (AGENT_CONTRACTS.json). Pre-Flight Sandbox = a mode of the Interviewer session, not a new speaker (D12).

**Agent roster:**
| Agent | Voice | Trigger | Output |
|---|---|---|---|
| Manager Agent | user-facing only | user goal | assignments, frozen rubric, enriched JD embedding (hidden context — D14), per-candidate interview brief, decisions |
| Sourcing/Screening sub-agent | none | new resumes / task | ranked list + similarity + parsed profiles (vs enriched JD embedding) |
| Scheduling sub-agent | none | shortlist | confirmed slot (incl. sandbox window), calendar invite, confirm/conflict report (email trigger routed via Manager Agent) |
| Interviewer sub-agent | candidate-facing only | dispatch + slot | transcript, per-question ratings + difficulty_estimate, anomaly flags, confidence, post-call report; runs Pre-Flight Sandbox first |
| Analytics/Scorecard sub-agent | none | post-call report | Extractive Evaluation scorecard: validated verbatim quotes → demonstrated level (L1/L2/L3/insufficient_evidence) |
| Communication sub-agent | none | Manager approval | sent candidate email + delivery confirmation |

**Fairness model:** same evaluation standard + difficulty level (L1/L2/L3, set once per role) for all candidates of a role. Never the same questions — always personalized per candidate (no question bank), always adaptive to real-time answers. Prosody policy (D16): paralinguistic signals for turn-taking only, never scoring.

**Interviewer pre-dispatch checklist (Manager-owned, all blocking):** 1 evaluation standard → frozen rubric · 2 per-candidate interview brief (Ollama/Llama 3.1, async) · 3 difficulty calibration (per role) · 4 no question bank · 5 bias guardrails + prosody policy · 6 confidence threshold → `[NEEDS_HUMAN_REVIEW]` · 7 immutable audit trail (incl. per-question difficulty_estimate).

**Manager reporting flow (user only):** async digest email · on-demand email query (`[STALE: re-run Scorecard?]` flag; no re-runs unless stale) · live reporting meeting (free-chain loop via WebRTC; latest Supabase state; no sub-agent re-runs mid-call; VAD barge-in) · auto-escalations (low confidence, double-conflict, no qualified candidates after N cycles, review-limit exceeded).

**Startup sequence:** 1 user sets goal + difficulty → Manager creates LangGraph task graph · 2 goal + structured rubric persisted to Supabase (frozen from first Interviewer dispatch) · 3 Dynamic Context Injection: allowlisted employer-source scrape → Ollama-distilled hidden-context appendix → enriched JD embedding, frozen (D14/D17) · 4 Sourcing/Screening dispatched async · 5 sub-agents write results to Supabase + emit completion events · 6 aggregate → Scheduling → brief generation → Interviewer dispatch (Pre-Flight Sandbox → interview) → Scorecard (Extractive Evaluation) → Communication · 7 digest at fixed cadence + every milestone; Fairness & Bias Lens aggregates continuously.

**Consent/recording:** every WebRTC call (both contexts, sandbox included) requires consent announced at call start; self-hosted recording = compliance fully in-house. Demographics for the Bias Lens: optional, self-reported, segregated, aggregate-only (GDPR Art. 9 class — D15).

**Docs:** 01-PRD · 02-ARCHITECTURE · 03-AGENT-SPECS · 04-API-EVENT-CONTRACT · 05-SPRINT-PLAN · 06-RISK-REGISTER · AGENT_CONTRACTS.json (v1.1.0, locked) · DECISIONS.md (D1–D17) · GLOSSARY.md.
