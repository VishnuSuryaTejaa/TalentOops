# Deliverable 4 — API/Event Contract (Manager ↔ sub-agent, JSON shape only)

Transport-agnostic JSON messages, all persisted to the Supabase `events` table (replayable). 
Consent/recording legality: a candidate-call `task.result` is valid only with `call_meta.consent_acknowledged = true`.

## 4.1 Envelope (every message)
```json
{
  "msg_id": "uuid",
  "ts": "ISO-8601",
  "from": "manager | sourcing_screening | scheduling | interviewer | scorecard | communication",
  "to":   "manager | sourcing_screening | scheduling | interviewer | scorecard | communication",
  "type": "task.assign | task.result | task.error | event.completion | escalation",
  "role_id": "uuid",
  "candidate_id": "uuid | null",
  "voice_context": "user | candidate | null",
  "payload": {}
}
```
**Voice ownership rule (message-level enforcement):** `voice_context: "user"` is valid only on messages where the speaking party is `manager`; `voice_context: "candidate"` only where it is `interviewer`. Any other combination is rejected at validation — no agent ever appears in the other's voice context.

## 4.2 `task.assign` payloads (Manager Agent → sub-agent)
```json
"sourcing_screening": { "jd_ref": "uuid", "enriched_jd_embedding_ref": "uuid (JD + frozen hidden-context appendix)",
                        "hidden_context_ref": "uuid | null", "corpus_ref": "uuid",
                        "similarity_floor": "number [TBD]", "batch_size": "int" }

"scheduling":         { "candidate_id": "uuid", "panel_calendar_refs": ["string"],
                        "slot_window": { "start": "ISO-8601", "end": "ISO-8601" }, "duration_min": "int" }

"interviewer":        { "rubric_ref": "uuid (frozen rubric)",
                        "difficulty_level": "L1 | L2 | L3",
                        "interview_brief_ref": "uuid (per-candidate interview brief)",
                        "candidate_profile_ref": "uuid", "resume_ref": "uuid",
                        "meeting_ref": "webrtc session id",
                        "bias_guardrails": { "protected_attributes_blocklist": ["string"], "evidence_only": true,
                                             "prosody_scoring": false },
                        "sandbox": { "enabled": "bool", "duration_sec": 120, "graded": false },
                        "confidence_threshold": "number 0.0–1.0 [TBD]" }

"scorecard":          { "transcript_ref": "uuid", "rubric_ref": "uuid", "candidate_id": "uuid" }

"communication":      { "decision": "invite | reject | offer", "template_ref": "uuid",
                        "candidate_id": "uuid", "requires_user_approval": "bool (true for offer)" }
```

## 4.3 `task.result` payloads (sub-agent → Manager Agent)
```json
"sourcing_screening": { "batch_id": "uuid",
                        "candidates": [ { "candidate_id": "uuid", "similarity_score": "number",
                                          "profile_ref": "uuid", "screening_notes": "string" } ] }

"scheduling":         { "candidate_id": "uuid", "status": "confirmed | conflict | rejected",
                        "slot": { "start": "ISO-8601", "end": "ISO-8601" },
                        "calendar_event_ref": "string", "conflict_count": "int" }

"interviewer":        { "candidate_id": "uuid", "transcript_ref": "uuid (immutable)",
                        "questions": [ { "q_id": "uuid", "ts": "ISO-8601", "competency_id": "string",
                                         "question_text_ref": "uuid", "rating": "number",
                                         "difficulty_estimate": "number (feeds Fairness & Bias Lens)",
                                         "confidence": "number 0.0–1.0", "flags": ["string"] } ],
                        "anomaly_flags": ["string"],
                        "rubric_coverage": [ { "competency_id": "string", "covered": "bool" } ],
                        "needs_human_review": "bool",
                        "call_meta": { "started_ts": "ISO-8601", "ended_ts": "ISO-8601",
                                       "consent_acknowledged": "bool",
                                       "sandbox_telemetry_ref": "uuid | null (non-graded, excluded from evaluation)" } }

"scorecard":          { "candidate_id": "uuid",
                        "scorecard": { "competencies": [ { "competency_id": "string",
                                                           "demonstrated_level": "L1 | L2 | L3 | insufficient_evidence",
                                                           "evidence_quotes": [ { "quote": "verbatim string",
                                                                                  "char_start": "int", "char_end": "int",
                                                                                  "speaker": "candidate | interviewer",
                                                                                  "validated": "bool (substring-matched)" } ] } ],
                                       "overall_fit": "number", "needs_human_review": "bool" } }

"communication":      { "candidate_id": "uuid", "email_type": "invite | reject | offer",
                        "status": "sent | bounced | failed", "message_id": "string" }
```

## 4.4 `escalation` payload (any agent → Manager Agent; Manager Agent → user via Gmail)
```json
{ "reason": "low_confidence | double_conflict | no_qualified_candidates | review_limit_exceeded | delivery_failure | protected_attribute_flag",
  "details_ref": "uuid", "candidate_id": "uuid | null" }
```

## 4.5 `event.completion` payload
```json
{ "task_ref": "uuid", "status": "done | partial | failed", "result_ref": "uuid | null" }
```
