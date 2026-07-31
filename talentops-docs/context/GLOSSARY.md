# GLOSSARY.md — fixed terminology. No synonyms, no drift.

| Term | Definition |
|---|---|
| **TalentOps** | The system: Manager Agent + 5 sub-agents running recruitment pipelines end-to-end. |
| **Manager Agent** | LangGraph supervisor; sole user-facing agent; owns dispatch, decisions, reporting, escalation. Never speaks to a candidate. |
| **Interviewer sub-agent** | Conducts candidate interview calls; candidate-facing voice only. Never speaks to the user. |
| **Sourcing/Screening sub-agent** | Text-only; ranks resume corpus against JD embedding (pgvector); outputs ranked list + parsed candidate profiles. |
| **Scheduling sub-agent** | Text-only; books interview slots via Google Calendar API. |
| **Analytics/Scorecard sub-agent** | Text-only; converts transcript + evaluation standard into a structured scorecard. |
| **Communication sub-agent** | Text-only; sends candidate emails (invite/reject/offer) via Gmail API on Manager Agent approval. |
| **voice ownership rule** | Absolute: user-facing calls/reporting meetings → Manager Agent speaks only; candidate interview calls → Interviewer sub-agent speaks only. Never crossed, never reinterpreted. |
| **evaluation standard** | What the user says matters for the role (e.g. "strong DSA, system design, 2+ years production Python"); converted by the Manager Agent into a structured rubric. |
| **difficulty level** | L1 junior / L2 mid / L3 senior; set once per role by the user; identical rigor for all candidates of that role. |
| **per-candidate interview brief** | Manager-generated (Groq Llama 3.3 70B, async/offline — D18) tailored brief per candidate: competencies to probe, depth, resume claims to verify, gaps/red flags. |
| **frozen rubric** | The structured rubric (competency categories + difficulty level) persisted to Supabase at goal intake; immutable from the first Interviewer sub-agent dispatch for the role. |
| **`[NEEDS_HUMAN_REVIEW]`** | Marker on any assessment whose self-rated confidence falls below threshold; routed to the user. |
| **`[STALE: re-run Scorecard?]`** | Manager Agent flag on email-query answers backed by outdated data. |
| **completion event** | Event a sub-agent emits after writing results to Supabase; what the Manager Agent aggregates on. |
| **Gemini Live API** | Primary voice model: `gemini-3.1-flash-live-preview` (fallback: `gemini-2.5-flash-native-audio`); native audio-in/audio-out via WebRTC; used in both voice contexts (D18/D19); conversational interface only — Gemini Live is explicitly prohibited from producing scoring or competency-level output (see Hybrid Loop). |
| **Hybrid Loop** | Two-phase architecture (D19) for bias-safe evaluation: Phase 1 (live) — `gemini-3.1-flash-live-preview` conducts the audio conversation and auto-generates a raw text transcript; Phase 2 (async/offline) — that raw text transcript is fed to the Analytics/Scorecard sub-agent (Groq Llama 3.3 70B / Groq Llama 3.3 70B) which performs ALL evaluation exclusively on text. The text transcript is the structural blind wall between voice and scorer (same enforcement class as D17’s STT boundary). |
| **Optimized Free-Chain** | *(Retired — D18)* Former voice stack (D17): Silero VAD → Groq Whisper STT → Groq Llama → self-hosted Kokoro TTS. Fully replaced by the Gemini Live API. |

| **WebRTC** | Self-hosted, open-source Google Meet bot handling all meeting joins + WebRTC audio bridging for both voice contexts (D17/D18); relays audio between Google Meet and the Gemini Live API WebRTC session; replaces Recall.ai. |
| **Pre-Flight Sandbox** | 2-minute non-graded calibration mode of the Interviewer sub-agent's candidate-context session, before the official interview: network/latency calibration + candidate anxiety reduction; telemetry gate: bad RTT/jitter → reschedule; data excluded from evaluation (D12). |
| **hidden context** | Groq Llama 3.3 70B-distilled appendix (async — D18) scraped from employer-controlled sources (domain, tech blog, GitHub org); appended to the JD embedding → **enriched JD embedding**; frozen with the rubric (D14, executor updated by D18). |
| **Extractive Evaluation** | Mandatory Analytics/Scorecard protocol: extract verbatim, substring-validated transcript quotes per competency BEFORE computing the demonstrated level (L1/L2/L3); no validated quote → `insufficient_evidence` (D13). |
| **Fairness & Bias Lens** | Dashboard heatmap correlating candidate cohorts (optional self-reported demographics, segregated) with question-difficulty telemetry; k-anonymized, aggregate-only; audits the Interviewer sub-agent for probing bias (D15). |
| **prosody policy** | Paralinguistic signals (tone, hesitation) drive turn-taking only — never evaluation evidence; all scoring is transcript-text-grounded (D16). Enforcement under D19 (Hybrid Loop): structurally enforced — Gemini Live’s raw text transcript output is passed to the text-only scorer (Groq/Llama 3.3 70B), which has no access to audio; paralinguistics are absent from the text by construction. System-prompt instruction alone is explicitly rejected as insufficient given Gemini Live’s native “Affective dialog” capability (D19). |
