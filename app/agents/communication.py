"""Communication capability: candidate-facing emails.

Email invitations include a TalentOops Interview Room URL.
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.email_client import get_email_client
from app.services.database import db
from app.supabase_client import log_event

logger = logging.getLogger("talentops.communication")

DECISION_COPY = {
    "STRONG_HIRE": "Strong Hire — Moving forward to offer stage",
    "HIRE": "Hire — Proceeding to final team review",
    "HOLD_FOR_REVIEW": "Under Review — We are currently completing interviews for this position",
    "REJECT": "Application Status Update — We will not be moving forward at this time",
}


from app.services.parser import clean_candidate_name


def _resolve_candidate_name(candidate: str) -> str:
    """Resolve actual candidate full name from database if given a candidate ID."""
    if not candidate or not isinstance(candidate, str):
        return "Candidate"
    try:
        cand_rows = db.query_sync("candidates", id=candidate)
        if cand_rows and cand_rows[0].get("name"):
            return cand_rows[0]["name"]
    except Exception:
        pass
    return clean_candidate_name(candidate) or "Candidate"


from app.config import settings
from app.services.llm_clients import openrouter_chat, groq_chat

async def _invite_body_llm(candidate: str, slot: str, room_url: str | None = None) -> tuple[str, str]:
    display_name = _resolve_candidate_name(candidate)
    
    context = ""
    try:
        cand_rows = db.query_sync("candidates", id=candidate)
        if cand_rows and cand_rows[0].get("profile"):
            context = str(cand_rows[0]["profile"])
    except Exception:
        pass

    prompt = f"""You are an expert recruiter writing a professional interview invitation email.
Candidate Name: {display_name}
Proposed Time: {slot}
Interview Room URL: {room_url or 'TBD'}
Candidate Profile Context: {context}

Write a professional, warm, and concise interview invitation email. 
Ensure it includes the room URL and mentions the proposed time.
Output ONLY the email body in plain text.
"""
    try:
        messages = [{"role": "user", "content": prompt}]
        if settings.LLM_PROVIDER == "groq" and (settings.GROQ_API_KEY or getattr(settings, "GROQ_API_KEY2", "")):
            body = await groq_chat(messages)
        elif settings.OPENROUTER_API_KEY:
            body = await openrouter_chat(messages)
        else:
            return _invite_body(candidate, slot, room_url)
            
        subject = f"Interview Invitation - Next Steps for {display_name}"
        if not body or len(body.strip()) < 10:
            return _invite_body(candidate, slot, room_url)
        return subject, body.strip()
    except Exception as exc:
        logger.warning("LLM generation failed in _invite_body_llm: %s", exc)
        return _invite_body(candidate, slot, room_url)

def _invite_body(
    candidate: str,
    slot: str,
    room_url: str | None = None,
) -> tuple[str, str]:
    display_name = _resolve_candidate_name(candidate)
    subject = "Interview invitation — next steps"
    room_info = (
        f"TalentOops Interview Room: {room_url}\n"
        f"Simply click the link above at your scheduled time — no external software required.\n"
        if room_url
        else ""
    )
    body = (
        f"Hi {display_name},\n\n"
        f"Thank you for your application. We'd like to invite you to an interview.\n"
        f"Proposed time: {slot}.\n\n"
        f"{room_info}"
        f"This session will be recorded for evaluation; consent will be confirmed "
        f"at the start of the call.\n\n"
        f"Best regards,\nThe Hiring Team"
    )
    return subject, body


def _rejection_body(candidate: str) -> tuple[str, str]:
    display_name = _resolve_candidate_name(candidate)
    subject = "Update on your application"
    body = (
        f"Hi {display_name},\n\n"
        f"Thank you for taking the time to apply. After careful review against a "
        f"consistent evaluation standard, we won't be moving forward at this time.\n\n"
        f"We wish you the best in your search.\n\nRegards,\nThe Hiring Team"
    )
    return subject, body


def _decision_body(candidate: str, decision: str) -> tuple[str, str]:
    display_name = _resolve_candidate_name(candidate)
    human_decision = DECISION_COPY.get(decision.upper(), decision)
    subject = f"Interview outcome — {human_decision}"
    body = (
        f"Hi {display_name},\n\n"
        f"Following your interview, the current outcome is: {human_decision}.\n\n"
        f"Regards,\nThe Hiring Team"
    )
    return subject, body


def _address_for(candidate: str, candidate_email: str | None = None) -> str:
    if candidate_email and "@" in candidate_email:
        return candidate_email
    if candidate and "@" in candidate:
        return candidate

    # Try database lookup
    if candidate and isinstance(candidate, str):
        try:
            cand_rows = db.query_sync("candidates", id=candidate)
            if cand_rows and cand_rows[0].get("email") and "@" in cand_rows[0]["email"]:
                return cand_rows[0]["email"]
        except Exception:
            pass

        safe_name = candidate.lower().replace(" ", ".")
        logger.warning("No stored email in database for candidate '%s', using fallback %s@example.com", candidate, safe_name)
        return f"{safe_name}@example.com"

    raise ValueError(f"Invalid or missing candidate email for '{candidate}'. Cannot send email.")


def _send(
    run_id: str,
    kind: str,
    candidate: str,
    subject: str,
    body: str,
    candidate_email: str | None = None,
) -> dict[str, Any]:
    target_address = _address_for(candidate, candidate_email)
    client = get_email_client()

    # Idempotency check: Check if email of this kind was already sent to target_address in this run
    try:
        events = db.query_sync("events", run_id=run_id, source="communication", event_type="email_sent")
        for ev in events:
            p = ev.get("payload", {})
            if p.get("kind") == kind and p.get("to") == target_address:
                logger.warning("Idempotency guard: Email '%s' already sent to %s for run %s. Skipping duplicate send.", kind, target_address, run_id)
                return {"kind": kind, "to": target_address, "message_id": p.get("message_id", "duplicate-skipped"), "subject": subject, "skipped": True}
    except Exception as exc:
        logger.debug("Idempotency check event query failed: %s", exc)

    # client.send() already dispatches over SMTPEmailClient when configured
    msg = client.send(to=target_address, subject=subject, body=body)

    log_event(
        run_id, source="communication", event_type="email_sent",
        payload={"kind": kind, "to": msg.to, "subject": subject, "message_id": msg.message_id},
    )
    return {"kind": kind, "to": msg.to, "message_id": msg.message_id, "subject": subject}


async def send_invite(
    run_id: str,
    candidate: str,
    slot: str,
    room_url: str | None = None,
    candidate_email: str | None = None,
) -> dict[str, Any]:
    """Send an interview invitation email with a TalentOops room URL."""
    subject, body = await _invite_body_llm(candidate, slot, room_url)
    return _send(run_id, "invite", candidate, subject, body, candidate_email)


def send_rejection(run_id: str, candidate: str, candidate_email: str | None = None) -> dict[str, Any]:
    subject, body = _rejection_body(candidate)
    return _send(run_id, "rejection", candidate, subject, body, candidate_email)


def send_decision(run_id: str, candidate: str, decision: str, candidate_email: str | None = None) -> dict[str, Any]:
    subject, body = _decision_body(candidate, decision)
    return _send(run_id, "decision", candidate, subject, body, candidate_email)
