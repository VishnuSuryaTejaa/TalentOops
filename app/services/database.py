"""Async data layer: thin supabase-py delegation with enforced remote tables."""
from __future__ import annotations

import uuid
import logging
from typing import Any
from app.config import settings
from app.services.logging import get_logger, get_request_id

logger = None
metrics_collector = None


class TranscriptFinalizedError(Exception):
    """Raised on transcript append after finalize (immutability guarantee)."""


class Database:
    def __init__(self) -> None:
        self._finalized: set[str] = set()
        global logger, metrics_collector
        if logger is None:
            from app.services.logging import get_metrics
            logger = get_logger(__name__)
            metrics_collector = get_metrics()

    async def insert(self, table: str, row: dict) -> dict:
        """Insert a row into the database."""
        try:
            data = self._sb().table(table).insert(row).execute().data
            return data[0] if data else row
        except Exception as e:
            if logger:
                logger.error(
                    "Remote table '%s' insert failed (%s: %s)",
                    table, type(e).__name__, str(e).splitlines()[0] if str(e) else ""
                )
            if metrics_collector:
                metrics_collector.increment_error_count("database", "insert")
            raise

    async def update(self, table: str, row_id: str | dict, patch: dict, id_column: str = "id") -> dict | None:
        """Update a row in the database."""
        try:
            query = self._sb().table(table).update(patch)
            if isinstance(row_id, dict):
                for k, v in row_id.items():
                    query = query.eq(k, v)
            else:
                query = query.eq(id_column, row_id)
            data = query.execute().data
            return data[0] if data else None
        except Exception as e:
            if logger:
                logger.error(
                    "Remote table '%s' update failed (%s: %s)",
                    table, type(e).__name__, str(e).splitlines()[0] if str(e) else ""
                )
            if metrics_collector:
                metrics_collector.increment_error_count("database", "update")
            raise

    async def get(self, table: str, row_id: str) -> dict | None:
        """Fetch a row from database."""
        data = self._sb().table(table).select("*").eq("id", row_id).execute().data
        return data[0] if data else None

    async def query(self, table: str, **eq: Any) -> list[dict]:
        """Query rows from database."""
        q = self._sb().table(table).select("*")
        for k, v in eq.items():
            q = q.eq(k, v)
        data = q.execute().data
        return data if data is not None else []

    def query_sync(self, table: str, **eq: Any) -> list[dict]:
        """Query rows synchronously from database."""
        try:
            q = self._sb().table(table).select("*")
            for k, v in eq.items():
                q = q.eq(k, v)
            data = q.execute().data
            return data if data is not None else []
        except Exception as e:
            if logger:
                logger.error(
                    "Remote table '%s' query_sync failed (%s: %s)",
                    table, type(e).__name__, str(e).splitlines()[0] if str(e) else ""
                )
            return []

    def get_sync(self, table: str, row_id: str) -> dict | None:
        """Fetch a row synchronously from database."""
        try:
            data = self._sb().table(table).select("*").eq("id", row_id).execute().data
            return data[0] if data else None
        except Exception:
            return None

    def insert_sync(self, table: str, row: dict) -> dict:
        """Insert a row synchronously into database."""
        try:
            data = self._sb().table(table).insert(row).execute().data
            return data[0] if data else row
        except Exception as e:
            if logger:
                logger.error(
                    "Remote table '%s' insert_sync failed (%s: %s)",
                    table, type(e).__name__, str(e).splitlines()[0] if str(e) else ""
                )
            raise

    async def append_transcript(self, interview_id: str, chunk: dict) -> None:
        if interview_id in self._finalized:
            raise TranscriptFinalizedError(interview_id)

        from datetime import datetime, timezone
        row = await self.get("interviews", interview_id)
        if row:
            t_list = row.get("transcript") or []
            t_list.append(dict(chunk))
            await self.update("interviews", interview_id, {"transcript": t_list})
        else:
            try:
                await self.insert("interviews", {
                    "id": interview_id,
                    "transcript": [dict(chunk)],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as exc:
                if logger:
                    logger.warning("Could not auto-create interviews row for %s: %s", interview_id, exc)

    async def finalize_transcript(self, interview_id: str) -> None:
        self._finalized.add(interview_id)

    async def get_transcript_chunks(self, interview_id: str) -> list[dict]:
        row = await self.get("interviews", interview_id)
        if row:
            return row.get("transcript") or []
            
        return []

    async def get_transcript_text(self, interview_id: str) -> str:
        chunks = await self.get_transcript_chunks(interview_id)
        return "\n".join(f"{c.get('speaker', '?')}: {c.get('text', '')}" for c in chunks)

    def _sb(self):
        from supabase import create_client
        if not settings.supabase_configured:
            raise ValueError("Supabase is not configured. Enforcing REAL API execution.")
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


db = Database()
