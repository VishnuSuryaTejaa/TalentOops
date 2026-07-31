# Deliverable 2 — System Architecture (rev 4: API-based free stack — D18)

## 2.1 Component layout (mono-stack: Pure Python — D10; API-based free tier — D18)

```
User ── React/Vite dashboard (incl. Fairness & Bias Lens) ──┐    Gmail ⇄ digests / email queries
User ── Google Meet (reporting) ⇄ WebRTC client (self-hosted) [Manager voice · user context]
                                                            │
        ┌───────────────────────────────────────────────────▼──────────────┐
        │ FastAPI monolith (Python 3.12+, uvicorn async workers)            │
        │  • LangGraph supervisor graph: Manager Agent + 5 sub-agents       │
        │  • Webhook routers: WebRTC · Gmail push · Calendar (in-proc)        │
        │  • Gemini Live session manager: WebRTC audio ⇄ WebRTC ⇄ Gemini Live  │
        │    (`gemini-3.1-flash-live-preview` — conversational only; D19)   │
        │    Phase 1 (live): audio conversation + auto-transcript generation │
        │    Phase 2 (async): raw transcript → Groq/Llama 3.3 70B for scoring     │
        │  • asyncio.TaskGroup / BackgroundTasks (no Celery, Redis, Node)   │
        │  • Session broker: issues voice sessions keyed by voice_context   │
        └───────┬────────────────────────────────┬─────────────────────────┘
                │ SQL / pgvector / events        │ async heavy reasoning (text-only)
   ┌────────────▼──────────┐          ┌──────────▼─────────────────────────┐
   │ Supabase + pgvector   │          │ Groq (Llama 3.3 70B) — briefs,      │
   │ state · events ·      │          │ rubrics, hidden-context distillation  │
   │ immutable audit ·     │          │ Groq (NVIDIA Llama 3.3 70B) —         │
   │ demographics* (§2.6)  │          │ Extractive Evaluation scorecard       │
   └───────────────────────┘          │ (async/offline only — never in the    │
                                      │  live voice path)                      │
                                      └────────────────────────────────────┘
                                             ↑
                                Gemini Live API (cloud, WebRTC)
                            native audio ⇄ WebRTC ⇄ Google Meet
Candidate ── Google Meet (interview) ⇄ WebRTC client (self-hosted) [Interviewer voice · candidate context]
* demographics: segregated, self-reported, aggregate-only — never agent-readable (§2.6)
```

**Mono-stack rationale (D10):** Node/Express gateway eliminated. Single serialization domain (native Python objects end-to-end), zero cross-runtime IPC/context switching; webhooks, Gemini Live session management, and background work all in FastAPI async routes + `asyncio.TaskGroup`. Python chosen over TypeScript: LangGraph's canonical/most mature runtime, ML-native tooling, first-class Supabase/pgvector clients. Horizontal scale = stateless uvicorn workers; shared state and LangGraph checkpoints in Supabase/Postgres.

## 2.2 Model & voice services (rev 5 — D18/D19: Hybrid Loop API stack)
| Concern | Service | Used by |
|---|---|---|
| **Phase 1 — Live audio conversation (voice-in/voice-out + auto-transcript)** | **`gemini-3.1-flash-live-preview`** via WebRTC (fallback: `gemini-2.5-flash-native-audio`; D19) | Both voice contexts (Manager user meetings; Interviewer candidate calls); conversational interface only — no scoring output |
| Meeting transport (join/leave lifecycle, WebRTC audio bridging to Gemini Live) | WebRTC client (self-hosted, open-source Google Meet bot) | Both voice contexts |
| **Phase 2 — Scoring (async/offline; receives text transcript only):** rubric structuring, per-candidate brief, hidden-context distillation, Extractive Evaluation | **Groq Free Tier — Llama 3.3 70B** (~1000 tokens/s; D18/D19) | Manager Agent (briefs, rubrics, distillation); Analytics/Scorecard sub-agent (Extractive Evaluation scoring) |
| **Phase 2 — Complex scorecard synthesis** (Groq primary; Groq fallback) | **Groq Free Tier — NVIDIA Llama 3.3 70B** (fallback: Groq Llama 3.3 70B; D18) | Analytics/Scorecard sub-agent; async/offline only |
| **Rejected (D17)** | GPT-4o Realtime, Moshi, Qwen2-Audio, ElevenLabs | — |
| **Eliminated (D18)** | Silero VAD; Groq Whisper STT; Groq Llama (in-call); self-hosted Kokoro TTS; locally hosted Ollama/Llama 3.1 | — |

- **Hybrid Loop (D19):** Candidate → Google Meet → WebRTC → WebRTC → `gemini-3.1-flash-live-preview` (live audio conversation) → Gemini Live auto-generates raw text transcript → text transcript written to Supabase `interviews` table (immutable) → Analytics/Scorecard sub-agent picks up transcript (text only) → Groq/Llama 3.3 70B performs ALL evaluation on text. Gemini Live produces NO scoring output. The text transcript is the structural blind wall between voice and scorer.
- Target end-to-end turn latency: **≤800 ms P50 / ≤1.5 s P95** (D18/D19; accounts for full routing path: Candidate → Google Meet → WebRTC → FastAPI → Gemini API → return; measured in S4).
- Transcripts sourced from the **Gemini Live API auto-generated transcript stream** → immutable audit trail in Supabase.
- **Prosody policy (D16, structural enforcement restored — D19):** Gemini Live features native “Affective dialog” and processes paralinguistics. System-prompt instruction alone is insufficient and explicitly rejected (D19). Structural enforcement: the text transcript passed to the scorer contains NO audio — paralinguistics are absent by construction. Gemini Live’s “affective” processing drives only conversational flow (turn-taking, barge-in), never evaluation. All scoring is transcript-text-grounded via Extractive Evaluation.
- **Cost structure (D18/D19):** Gemini Live API (voice) + Groq Llama 3.3 70B (heavy reasoning/scoring) + Groq Llama 3.3 70B (scorecard) are all free-tier hosted APIs. Zero self-hosted GPU requirement. Caveats: [ASSUME: Gemini Live free-tier concurrent session limits acceptable; fallback to `gemini-2.5-flash-native-audio` on quota or model unavailability]; [ASSUME: Groq RPM limits acceptable for async brief batch; retry/backoff implemented]; [ASSUME: Groq Llama 3.3 70B free availability stable; fallback to Groq Llama 3.3 70B].

## 2.3 Voice ownership rule — architectural enforcement (absolute, unchanged)
| Voice context | Who speaks | Who listens |
|---|---|---|
| User-facing calls / reporting meetings | Manager Agent only | User |
| Candidate interview calls | Interviewer sub-agent only | Candidate |

Never crossed, never reinterpreted. Enforcement point is now the **session broker** in the FastAPI monolith: voice-chain sessions (WebRTC client + free-chain pipeline) are issued keyed by `voice_context`; the Manager Agent runtime cannot obtain a `candidate` session and the Interviewer sub-agent runtime cannot obtain a `user` session. Message-level validation unchanged (§4.1). The Pre-Flight Sandbox runs inside the Interviewer sub-agent's candidate-context session (D12) — no new speaker identity is introduced.

## 2.4 Data flow (rev 2)
1. User sets goal + difficulty level (dashboard/CLI) → Manager Agent creates LangGraph task graph.
2. Manager Agent persists goal + structured rubric (evaluation standard) to Supabase; rubric frozen (immutable) no later than first Interviewer sub-agent dispatch for the role.
3. **Dynamic Context Injection (D14):** Manager Agent scrapes allowlisted employer-controlled sources (company domain, tech blog, GitHub org; robots.txt-compliant) → **Groq Llama 3.3 70B** distills a hidden-context appendix (internal design systems, preferred tech stacks, async/offline — D18) → appended to the JD embedding → **enriched JD embedding** (pgvector), frozen alongside the rubric so all candidates match against identical context.
4. Manager Agent dispatches Sourcing/Screening with the enriched JD embedding → ranked candidates + parsed profiles → Supabase → completion event.
5. Manager Agent shortlists → Scheduling sub-agent books slots, reports confirmation → Manager Agent assigns Communication sub-agent to send invites.
6. Per confirmed slot: Manager Agent generates per-candidate interview brief (**Groq Llama 3.3 70B**, async/offline — D18) → dispatches Interviewer sub-agent (pre-dispatch checklist, §3.4).
7. Candidate call: **Pre-Flight Sandbox** (2-min non-graded calibration, D12) → boundary announcement → official interview via **`gemini-3.1-flash-live-preview` WebRTC session** (live audio conversation — D19) → Gemini Live auto-generates raw text transcript → transcript written to immutable audit trail.
8. Analytics/Scorecard sub-agent receives raw text transcript (NO audio) → runs **Extractive Evaluation** (Groq Llama 3.3 70B / Groq Llama 3.3 70B, text-only — D19 Hybrid Loop) → Manager Agent decides → Communication sub-agent emails candidate.
9. Manager Agent digests + escalations (§3.1); Fairness & Bias Lens aggregates question telemetry continuously (§2.6).

## 2.5 Data stores (Supabase, rev 2)
| Table group | Contents | Notes |
|---|---|---|
| events | envelope log, workflow transitions | replayable append-only audit trail |
| rubrics | frozen evaluation standard, competencies | one frozen rubric per run |
| embeddings | pgvector store for JDs and candidate profiles | used for vector similarity matching |
| roles | goal, JD, difficulty level, frozen rubric | frozen (immutable) from first Interviewer dispatch |
| candidates | name, email, phone, parsed profile data (skills, experience, education), raw resume | linked to roles |
| projects | candidate projects, tech stack, URL | linked to candidates |
| interviews | transcript (Gemini Live STT stream), questions | immutable audit trail; user-retrievable |
| scorecards | per-competency demonstrated level + validated verbatim evidence quotes | output from Evaluator Agent |
| demographics | optional self-reported cohort data | segregated schema; RLS denies all agent roles; aggregate views only |
| calibration | Pre-Flight Sandbox telemetry: VAD baseline, RTT/jitter, audio levels | excluded from evaluation path |
| comms | outbound email logs | |
| interview_qa_logs | per-question transcript and confidence score | used for fine-grained analysis |
| hr_debrief_sessions | manager debrief meeting state, summary, context | drives the Manager Debrief GMeet session |

## 2.6 Fairness & Bias Lens (dashboard telemetry path — D15)
- **Inputs:** per-question `difficulty_estimate` + competency mapping from the Interviewer audit trail ⋈ optional, post-interview, self-reported demographics (segregated store).
- **Isolation invariants:** demographics never enter any agent context, prompt, or scoring path; join happens only in server-side aggregate views.
- **Output:** heatmap correlating candidate cohorts × question-difficulty distribution, with k-anonymity suppression (cells with n < k hidden, k [TBD]) and drift alerts when any cohort's mean difficulty deviates beyond threshold [TBD] — detective control auditing the Interviewer sub-agent for unintentional probing bias.

## 2.7 Flags
- Consent/recording legality: both voice contexts recorded via the self-hosted WebRTC client — consent announced and obtained at call start per jurisdiction (Pre-Flight Sandbox included); self-hosting shifts recording-compliance responsibility fully in-house (no vendor DPA to lean on).
- Demographic cohort data is special-category data (e.g., GDPR Art. 9): explicit opt-in, segregated storage, aggregate-only exposure.
