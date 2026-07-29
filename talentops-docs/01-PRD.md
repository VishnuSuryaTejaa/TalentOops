# Deliverable 1 — PRD: TalentOps

## 1.1 Problem
- Recruitment spans five disjointed activities (sourcing → screening → scheduling → interviewing → reporting) across disconnected tools; coordination cost lands on the hiring manager.
- Interview quality and difficulty vary by human interviewer → inconsistent, hard-to-defend evaluations.
- Manual screening of large resume volumes is slow and lossy; scheduling latency loses strong candidates.
- Evaluation evidence (what was asked, why, how it was scored) is rarely captured → no audit trail.

## 1.2 Solution (one line)
A Manager Agent (LangGraph supervisor) runs the full pipeline via 5 sub-agents under a user-set evaluation standard and difficulty level; the Interviewer sub-agent conducts adaptive voice interviews; all user-facing communication belongs to the Manager Agent (voice ownership rule — see Deliverable 2 §2.3).

## 1.3 Goals
| # | Goal | Measured by |
|---|---|---|
| G1 | End-to-end pipeline automation from user goal ("fill role X") to decision comms | User interventions per hire (target [TBD]) |
| G2 | Fair evaluation: same evaluation standard + difficulty level for all candidates of a role; questions always personalized per candidate and adaptive to real-time answers | Rubric coverage rate per interview; standard-drift incidents = 0 |
| G3 | Autonomous, natural voice interviews with full auditability | 100% interviews with stored transcript + per-question competency mapping |
| G4 | User oversight without user effort: digests, email Q&A, live reporting meetings | Digest delivery rate; query turnaround [TBD] |
| G5 | Safe autonomy: low-confidence and anomalous outcomes escalate to human | 100% of `[NEEDS_HUMAN_REVIEW]` items reviewed by user |

## 1.4 Non-goals (v1)
- Final offer authority — Manager Agent decides pipeline advancement; offer emails require explicit user approval. [ASSUME: user retains offer authority — see DECISIONS.md D2]
- External job-board sourcing — v1 operates on a provided resume corpus. [ASSUME: D3]
- Live coding / IDE assessment — interviews are verbal only. [ASSUME: D7]
- Video avatar/face for agents; salary negotiation; background checks; ATS integration.
- Multi-role optimization — one role per pipeline instance; parallel instances allowed. [ASSUME: D4]

## 1.5 Users
| User | Interaction |
|---|---|
| Hiring manager ("user") | Sets goal, evaluation standard, difficulty level; receives digests; email Q&A; live reporting meetings; approves offers |
| Candidate | Email comms + one voice interview with the Interviewer sub-agent |

## 1.6 Success metrics (numeric targets [TBD] — baselined during pilot)
- Time-to-shortlist; time-from-shortlist-to-interview
- % interviews flagged `[NEEDS_HUMAN_REVIEW]` (autonomy-quality proxy)
- Rubric competency coverage rate per interview
- Candidate drop-off rate between stages
- Cost per completed interview (Groq usage + self-hosted infra amortization; $0 base API cost — D17)
- Audit completeness: transcripts stored = 100% (hard requirement, not [TBD])

## 1.7 Constraints & flags
- Consent/recording legality: all Vexa-joined calls (candidate interviews and user reporting meetings) require jurisdiction-appropriate recording consent announced at call start; self-hosted recording = compliance responsibility fully in-house.
- Conversational voice loop runs on the Hybrid Loop API stack (Gemini Live API via WebRTC; turn latency ≤800 ms P50 / ≤1.5 s P95 — D18/D19); heavy reasoning (per-candidate interview brief, hidden-context distillation, Extractive Evaluation) is async/offline via Groq Llama 3.3 70B and OpenRouter Nemotron API. Locally hosted Ollama and local GPU requirements have been eliminated (D18).
