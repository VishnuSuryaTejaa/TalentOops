"""Groq chat clients."""
import asyncio
import httpx
import itertools
import logging

from app.config import settings

logger = logging.getLogger("talentops.llm_clients")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

_groq_request_counter = itertools.count()


def _configured_groq_keys() -> list[tuple[int, str]]:
    configured: list[tuple[int, str]] = []
    for key_number, key in enumerate(
        (
            getattr(settings, "GROQ_API_KEY", ""),
            getattr(settings, "GROQ_API_KEY2", ""),
            getattr(settings, "GROQ_API_KEY3", ""),
            getattr(settings, "GROQ_API_KEY4", ""),
        ),
        start=1,
    ):
        key = key.strip()
        if not key:
            logger.warning("Groq API key %d is not configured.", key_number)
            continue
        if not key.startswith("gsk_"):
            logger.warning("Groq API key %d is malformed and will be skipped.", key_number)
            continue
        configured.append((key_number, key))
    return configured


async def groq_chat(messages: list[dict], json_mode: bool = False, max_tokens: int | None = None, temperature: float | None = None) -> str:
    groq_keys = _configured_groq_keys()
    if not groq_keys:
        raise ValueError("No Groq API keys configured in environment.")

    _messages = list(messages)
    if json_mode:
        if _messages and _messages[0].get("role") == "system":
            _messages[0] = {"role": "system", "content": _messages[0].get("content", "") + "\n\nReturn valid JSON."}
        else:
            _messages.insert(0, {"role": "system", "content": "Return valid JSON."})

    body: dict = {"model": GROQ_MODEL, "messages": _messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if max_tokens:
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature

    last_error = None
    start_index = next(_groq_request_counter) % len(groq_keys)
    ordered_keys = groq_keys[start_index:] + groq_keys[:start_index]

    for attempt, (key_number, key) in enumerate(ordered_keys, start=1):
        headers = {"Authorization": f"Bearer {key}"}
        logger.info("Trying Groq API key %d (%d/%d).", key_number, attempt, len(ordered_keys))

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(GROQ_URL, json=body, headers=headers)
                r.raise_for_status()
                logger.info("Groq API key %d succeeded.", key_number)
                return r.json()["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            last_error = e
            logger.warning(
                "Groq API key %d failed with HTTP %d: %s; trying the next configured key.",
                key_number,
                e.response.status_code,
                e.response.text
            )

        except Exception as e:
            last_error = e
            logger.warning("Groq API key %d connection error: %s; trying the next key.", key_number, e)

    raise last_error or RuntimeError("Groq chat failed with all configured keys.")


