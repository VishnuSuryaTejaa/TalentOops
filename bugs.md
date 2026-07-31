# TalentOops Pipeline Audit & Bug Tracking

## Phase 1: Resume Upload & Candidate Ingestion
- **[FIXED] Name Extraction Fallback**: Enhanced `extract_candidate_metadata()` in `app/services/parser.py` to handle explicit label prefixes (`Name:`, `Full Name:`, `Applicant Name:`) and infer candidate name from email (e.g., `surya.tejaa@email.com` -> `Surya Tejaa`) when headers fail to yield a clean name.
- **[VERIFIED] Candidate Name in Communication**: Fixed email invitation and consent disclosure routines to resolve real candidate name from database before falling back to filename.
- **[VERIFIED] Supabase Candidates RLS Policy**: Verified RLS policy `"Allow all for candidates"` on `public.candidates` allowing `anon` and `authenticated` access.

## Phase 2: Pipeline State & Email Dispatch
- **[FIXED] Database Synchronous Methods Missing**: Added missing `query_sync()`, `get_sync()`, and `insert_sync()` methods to `Database` in `app/services/database.py`. Prevents `AttributeError` during synchronous email candidate lookup and idempotency verification.
- **[FIXED] Email Dispatch Idempotency Guard**: Restored idempotency check in `_send()` in `app/agents/communication.py` using `db.query_sync()`, preventing duplicate invite/rejection/decision email sends.
- **[FIXED] Candidate ID Preservation in Room Scheduling**: Fixed `run_scheduling()` in `app/agents/scheduling.py` to preserve the exact database candidate `id` (instead of slugifying `top_candidate`), allowing WebRTC room signaling and question generation to match records in `candidates` table.
- **[VERIFIED] Pipeline Transition & Meeting URL Generation**: Verified state transition from `Sourcing` -> `Scheduling` -> `WAITING_FOR_INTERVIEW`. Verified self-hosted TalentOops meeting URL generation format (`http://localhost:5173/interview/{room_id}`).

## Phase 3: Room Signaling & Interview Handshake
- **[FIXED] LLM Client Non-Retryable Error Handling**: Fixed `_post()` in `app/services/llm_clients.py` to break retry loops immediately on `401 Unauthorized`, `402 Payment Required`, or `404 Not Found` status codes instead of delaying execution with repeated failing retries.
- **[FIXED] Groq Free Fallback Models**: Updated `GROQ_FALLBACK_MODELS` in `app/services/llm_clients.py` with active free endpoints (`llama-3.3-70b-instruct:free`, `llama-3.2-3b-instruct:free`, `gemini-2.0-flash-exp:free`, `deepseek-r1:free`, `qwen-2.5-coder-32b-instruct:free`) and verified automatic failover to `groq_chat`.
- **[FIXED] TTS 401/403 Invalid Audio Payload Bug**: Fixed `_synthesize_google()` in `app/services/speech_engine.py` to return empty audio bytes `b""` (and `audio_b64 = None`) when API keys return 401/403/unconfigured instead of returning raw text bytes disguised as binary audio. This enables seamless fallback to browser Web Speech API (`speechSynthesis.speak()`) so the AI agent always talks.
- **[FIXED] Short / Vague Answer Technical Probing**: Enhanced `_generate_follow_up()` in `app/rooms/signaling.py` to automatically append technical detail probes when candidate gives short/vague answers.
- **[VERIFIED] WebSocket Handshake & Live Room Signals**: Verified `_InteractiveRoomSession` WebSocket connection flow, room joined frames, consent ask disclosure, dynamic question emission, and clean turn transitions.

## Phase 4: Interview Loop & Live Transcript
- **[FIXED] Auto-Creation of Missing Interviews Table Rows**: Updated `append_transcript()` in `app/services/database.py` to automatically insert a new row in the `interviews` table when `row` is `None` on Turn 0/1. Guarantees 100% reliable live transcript persistence to Supabase.
- **[VERIFIED] Live Q&A Log Persistence**: Verified real-time persistence of candidate turns to both `interviews.transcript` and `interview_qa_logs` table in Supabase.
- **[VERIFIED] Resume-Grounded Question Generation**: Verified `generate_dynamic_question()` in `app/agents/interviewer.py` incorporates extracted resume skills, projects, and summary context for targeted technical probing.
- **[VERIFIED] FSM State Machine & History Preservation**: Verified `InterviewerFSM` 8-stage lifecycle transitions, semantic duplicate rejection, and history context preservation across turns.

## Phase 5: Post-Interview Evaluation & Scorecard
- **[FIXED] Self-Hosted Debrief Link Propagation in Graph Nodes**: Fixed `reporting_node` in `app/graph/nodes.py` to invoke `create_manager_debrief_session()`, establishing an in-platform debrief room (`room_url`) and populating `debrief_id` in `hr_debrief_sessions` table in Supabase.
- **[VERIFIED] Automatic Evaluator Agent Triggering**: Verified that ending the WebSocket room session (`__END_SESSION__`) automatically triggers `EvaluatorAgent.evaluate_transcript()`, generating and broadcasting real-time evaluation scorecards.
- **[VERIFIED] Supabase `hr_debrief_sessions` Schema Integrity**: Verified `hr_debrief_sessions` table schema containing `debrief_id`, `interview_id`, `candidate_id`, `room_url`, `status`, `summary`, and `knowledge_context` with RLS policy enabled.
- **[VERIFIED] Scorecard Persistence & LLM Evaluation**: Verified scorecard creation in `scorecards` table with behavioral metrics, detailed competency quotes, transcript evaluations, and final hiring recommendations (`Strong Hire`, `Hire`, `Hold`, `Reject`).

## Phase 6: Frontend HR Dashboard & Reporting
- **[VERIFIED] Evaluation Endpoint Role Authorization**: Verified `GET /api/interviews/{interview_id}/evaluation` enforces `X-User-Role: hr` header authentication and delivers complete scorecard payloads (overall fit, behavioral metrics, detailed competencies, transcript evaluations, and final recommendation).
- **[VERIFIED] On-Demand Evaluation Fallback**: Verified backend on-demand scorecard generation from `interview_qa_logs` when a direct scorecard DB record is not yet present.
- **[VERIFIED] HR Debrief Session Endpoint**: Verified `GET /api/debrief/{interview_id}` and `POST /api/debrief/turn` endpoints for oral HR Q&A with the Manager AI Agent.
- **[VERIFIED] Frontend React Build & Component Rendering**: Verified production build of frontend SPA using Vite (`npm run build`), confirming zero bundle compilation errors in `HREvaluationDashboard.jsx`, `EvaluationReport.jsx`, `HRDebriefCard.jsx`, `ScorecardView.jsx`, and `InterviewRoom.jsx`.
