"""Groq / OpenRouter chat clients."""
import asyncio

import httpx

from app.config import settings

import logging

logger = logging.getLogger("talentops.llm_clients")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_FALLBACK_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
    "deepseek/deepseek-r1:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
]


async def _post(
    url: str,
    key: str,
    model: str,
    messages: list[dict],
    json_mode: bool,
    max_tokens: int | None = None,
    extra_headers: dict | None = None,
) -> str:
    body: dict = {"model": model, "messages": messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if max_tokens:
        body["max_tokens"] = max_tokens

    headers = {"Authorization": f"Bearer {key}"}
    if extra_headers:
        headers.update(extra_headers)

    last: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(url, json=body, headers=headers)
                if r.status_code in (401, 402, 404):
                    r.raise_for_status()
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            last = e
            if e.response.status_code in (401, 402, 404):
                # Non-retryable error (unauthorized, payment required, or model not found) — break immediately
                break
            await asyncio.sleep(0.5 * 2**attempt)
        except Exception as e:
            last = e
            await asyncio.sleep(0.5 * 2**attempt)
    raise last  # type: ignore[misc]


async def groq_chat(messages: list[dict], json_mode: bool = False, max_tokens: int | None = None) -> str:
    keys = [k for k in [getattr(settings, "GROQ_API_KEY", ""), getattr(settings, "GROQ_API_KEY2", "")] if k]
    if not keys:
        raise ValueError("No Groq API keys configured in environment.")

    last_error = None
    for key in keys:
        try:
            return await _post(GROQ_URL, key, GROQ_MODEL, messages, json_mode, max_tokens)
        except Exception as e:
            last_error = e
            continue

    raise last_error  # type: ignore[misc]


async def openrouter_chat(messages: list[dict], json_mode: bool = False, max_tokens: int | None = None) -> str:
    key = getattr(settings, "OPENROUTER_API_KEY", "") or ""
    if not key or "your-openrouter-api-key" in key:
        # If OpenRouter key is not set or placeholder, failover to groq_chat
        try:
            return await groq_chat(messages, json_mode, max_tokens)
        except Exception as exc:
            logger.warning("Failover to groq_chat failed: %s", exc)
        raise ValueError("OPENROUTER_API_KEY is not configured in environment.")

    extra_headers = {
        "HTTP-Referer": "https://talentops.local",
        "X-Title": "TalentOps",
    }

    last_error: Exception | None = None
    for model in OPENROUTER_FALLBACK_MODELS:
        try:
            return await _post(
                OPENROUTER_URL,
                key,
                model,
                messages,
                json_mode,
                max_tokens,
                extra_headers=extra_headers,
            )
        except Exception as exc:
            last_error = exc
            logger.warning("OpenRouter call failed for model %s: %s", model, exc)

    # If OpenRouter model calls failed, try failing over to groq_chat
    try:
        logger.info("OpenRouter model attempts failed — failing over to groq_chat")
        return await groq_chat(messages, json_mode, max_tokens)
    except Exception:
        pass

    raise last_error or RuntimeError("OpenRouter completion failed across all fallback models.")
