"""LLM client abstraction for supervisor and sub-agents."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Protocol

from app.config import get_settings

logger = logging.getLogger("talentops.llm")


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, schema_hint: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON object shaped like ``schema_hint``."""
        ...


_STOPWORDS = {
    "the", "and", "for", "with", "who", "has", "have", "that", "this", "from",
    "hire", "hiring", "candidate", "candidates", "years", "experience", "strong",
    "must", "should", "will", "able", "role", "team", "work", "a", "an", "of", "in", "to",
}


def _keywords(text: str, limit: int = 5) -> list[str]:
    seen: list[str] = []
    for raw in (text or "").lower().replace(",", " ").replace(".", " ").split():
        tok = raw.strip("()[]:;")
        if len(tok) > 3 and tok not in _STOPWORDS and tok not in seen:
            seen.append(tok)
        if len(seen) >= limit:
            break
    return seen


def _stable_float(seed: str, lo: float, hi: float) -> float:
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    return lo + (h % 10_000) / 10_000 * (hi - lo)





def _extract_json_object(text: str, schema_hint: dict[str, Any] | None = None) -> dict[str, Any]:
    text = (text or "").strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            p = part.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{") and p.endswith("}"):
                try:
                    return json.loads(p)
                except Exception:
                    pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
        try:
            return json.loads(json_str)
        except Exception:
            pass

    try:
        return json.loads(text)
    except Exception:
        raise


class RemoteLLMClient:
    def __init__(self, provider: str):
        settings = get_settings()
        from openai import OpenAI

        self.provider = provider
        self.settings = settings
        if provider == "groq":
            primary_key = settings.GROQ_API_KEY or getattr(settings, "GROQ_API_KEY2", "")
            self._client = OpenAI(api_key=primary_key, base_url="https://api.groq.com/openai/v1")
            self._model = "llama-3.3-70b-versatile"
        elif provider == "openrouter":
            self._client = OpenAI(api_key=settings.OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
            self._model = settings.llm_model if settings.llm_model else "meta-llama/llama-3.3-70b-instruct"
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    def complete_json(self, system: str, user: str, schema_hint: dict[str, Any]) -> dict[str, Any]:
        from openai import OpenAI
        keys = []
        if self.provider == "groq":
            keys = [k for k in [self.settings.GROQ_API_KEY, getattr(self.settings, "GROQ_API_KEY2", "")] if k]
        else:
            keys = [self.settings.OPENROUTER_API_KEY]

        last_error = None
        for key in keys:
            try:
                base_url = "https://api.groq.com/openai/v1" if self.provider == "groq" else "https://openrouter.ai/api/v1"
                client = OpenAI(api_key=key, base_url=base_url)
                resp = client.chat.completions.create(
                    model=self._model,
                    max_tokens=512,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": f"{system}\nReturn raw JSON object matching keys: {json.dumps(list(schema_hint.keys()))}"},
                        {"role": "user", "content": user},
                    ],
                )
                raw_content = resp.choices[0].message.content or "{}"
                return _extract_json_object(raw_content, schema_hint)
            except Exception as e:
                last_error = e
                logger.warning("Remote LLM call with key ending in ...%s failed: %s. Trying next key if available.", key[-4:] if len(key)>=4 else "", e)
                continue

        logger.error(
            "Remote LLM API call failed (model=%s). Error: %s",
            self._model, last_error,
        )
        raise RuntimeError(
            f"LLM API call failed (model={self._model}): {last_error}."
        ) from last_error


def get_llm_client() -> LLMClient:
    provider = get_settings().llm_provider
    return RemoteLLMClient(provider)

