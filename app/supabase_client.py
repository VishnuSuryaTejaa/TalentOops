"""Supabase-backed event logging.

The supabase-py client is synchronous, so all writes are pushed off the event
loop with ``asyncio.to_thread`` and fired as background ``asyncio`` tasks — the
supervisor graph never blocks on a DB round-trip. If Supabase is not configured
we fall back to structured stdout logging so the graph still boots and is
testable with zero credentials.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

import httpx

logger = logging.getLogger("talentops.events")

_pending: set[asyncio.Task] = set()
_client = None

def _get_client():
    global _client
    if _client is None:
        from app.config import get_settings
        settings = get_settings()
        if settings.supabase_configured:
            from supabase import create_client
            _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client

def _get_rest_url_and_headers():
    settings = get_settings()
    if not settings.supabase_configured:
        return None, None
    url = f"{settings.supabase_url.rstrip('/')}/rest/v1/events"
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    return url, headers


def _insert_sync(row: dict[str, Any]) -> None:
    # Synchronous fallback if needed (e.g., outside event loop)
    url, headers = _get_rest_url_and_headers()
    if not url:
        raise ValueError("Supabase is not configured. Enforcing REAL API execution.")
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(url, json=row, headers=headers)
            r.raise_for_status()
    except Exception as e:
        logger.error("[event:insert_failed] %s: %s", type(e).__name__, str(e))
        raise


async def _write(row: dict[str, Any]) -> None:
    url, headers = _get_rest_url_and_headers()
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=row, headers=headers)
            r.raise_for_status()
    except Exception as e:
        logger.exception("Failed to write event: %s | %s", row.get("event_type"), str(e))


def log_event(
    run_id: str,
    source: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Fire-and-forget: schedule an event write as a background asyncio task."""
    row = {
        "run_id": run_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "event_type": event_type,
        "payload": payload or {},
    }
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _insert_sync(row)
        return

    task = loop.create_task(_write(row))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def flush_events() -> None:
    """Await all in-flight event writes (call on shutdown / after a run)."""
    if _pending:
        await asyncio.gather(*list(_pending), return_exceptions=True)
