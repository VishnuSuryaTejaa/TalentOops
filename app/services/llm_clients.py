"""Groq / OpenRouter chat clients."""
import asyncio
import httpx
import itertools
import logging

from app.config import settings

logger = logging.getLogger("talentops.llm_clients")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Global state for cycling keys
_groq_keys = [k for k in [getattr(settings, "GROQ_API_KEY", ""), getattr(settings, "GROQ_API_KEY2", "")] if k]
_key_cycle = itertools.cycle(_groq_keys) if _groq_keys else None


async def groq_chat(messages: list[dict], json_mode: bool = False, max_tokens: int | None = None, temperature: float | None = None) -> str:
    if not _key_cycle:
        raise ValueError("No Groq API keys configured in environment.")

    _messages = list(messages)
    if json_mode:
        _messages.append({"role": "system", "content": "Return valid JSON."})

    body: dict = {"model": GROQ_MODEL, "messages": _messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if max_tokens:
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature

    last_error = None
    num_keys = len(_groq_keys)
    
    # Try up to 10 times total, cycling keys.
    for attempt in range(10):
        key = next(_key_cycle)
        headers = {"Authorization": f"Bearer {key}"}
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(GROQ_URL, json=body, headers=headers)
                if r.status_code in (401, 402, 404):
                    r.raise_for_status() # break out or fail
                
                # If 429, we will catch it in HTTPStatusError below
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
                
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code in (401, 402, 404):
                # Non-retryable
                break
            logger.warning("Groq API 429/5xx error on attempt %d. Switching key...", attempt + 1)
            # Sleep if we've cycled through all keys
            if attempt > 0 and attempt % num_keys == 0:
                await asyncio.sleep(1.5 ** (attempt // num_keys))
            else:
                await asyncio.sleep(0.5)

        except Exception as e:
            last_error = e
            logger.warning("Groq API connection error: %s. Retrying...", e)
            await asyncio.sleep(1)

    raise last_error or RuntimeError("Groq chat failed after retries.")


async def openrouter_chat(messages: list[dict], json_mode: bool = False, max_tokens: int | None = None, temperature: float | None = None) -> str:
    # User requested to skip OpenRouter and just use cycling groq keys for now
    logger.info("Redirecting openrouter_chat to groq_chat as per configuration.")
    return await groq_chat(messages, json_mode, max_tokens, temperature)
