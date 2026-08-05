"""Embedding generation for JD / candidate vector matching."""
from __future__ import annotations

import functools
import hashlib
import logging
import math
import time
from typing import Callable, Any, Protocol

from app.config import get_settings

logger = logging.getLogger("talentops.embedder")


def retry_with_backoff(max_retries: int = 3, initial_delay: float = 0.5, backoff_factor: float = 2.0):
    """Decorator to retry functions on transient errors / rate limits with exponential backoff."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    exc_str = str(exc).lower()
                    is_rate_limit_or_server_err = any(
                        err in exc_str for err in ["429", "rate limit", "too many requests", "500", "502", "503", "504", "server error"]
                    )
                    if not is_rate_limit_or_server_err and attempt == 1:
                        # Re-raise non-retryable errors immediately unless transient
                        logger.warning("Error in %s: %s (attempt %d/%d). Not a retryable error, failing fast.", func.__name__, exc, attempt, max_retries)
                        raise last_exc
                    if attempt == max_retries:
                        logger.error("%s failed after %d attempts: %s", func.__name__, max_retries, exc)
                        raise last_exc
                    logger.warning("%s encountered error: %s. Retrying in %.2fs (attempt %d/%d)...", func.__name__, exc, delay, attempt, max_retries)
                    time.sleep(delay)
                    delay *= backoff_factor
            if last_exc:
                raise last_exc
        return wrapper
    return decorator


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]:
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...



_EMBEDDING_CACHE: dict[str, list[float]] = {}


def _get_text_hash(text: str, dim: int) -> str:
    return hashlib.sha256(f"{dim}:{text or ''}".encode("utf-8")).hexdigest()


def _hash_embed(text: str, dim: int = 384) -> list[float]:
    """Fallback deterministic vector generator when remote embedding API is unavailable or out of credits."""
    import hashlib
    import math
    vec = []
    for i in range(dim):
        digest = hashlib.sha256(f"{i}:{text}".encode("utf-8")).digest()
        val = (digest[0] / 255.0) * 2.0 - 1.0
        vec.append(val)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class RemoteEmbedder:
    """OpenAI-compatible embeddings endpoint (lazy) with dimension constraint, vector normalization, and retries."""

    def __init__(self, provider: str):
        settings = get_settings()
        from openai import OpenAI

        # "remote" is an alias for "groq" — the default remote provider
        if provider in ("groq", "remote"):
            self._client = OpenAI(api_key=settings.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        else:
            raise ValueError(f"Unknown embed provider: {provider}")
        self.dim = settings.embed_dim
        self._model = "text-embedding-3-small"

    def _normalize(self, vec: list[float]) -> list[float]:
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @retry_with_backoff(max_retries=3, initial_delay=0.5)
    def embed(self, text: str) -> list[float]:
        cache_key = _get_text_hash(text, self.dim)
        if cache_key in _EMBEDDING_CACHE:
            return _EMBEDDING_CACHE[cache_key]

        try:
            if "api.groq.com" in str(self._client.base_url).lower():
                # Groq doesn't currently support an embeddings endpoint. Bypass to avoid latency and 404s.
                raise NotImplementedError("Groq does not support embeddings API.")

            kwargs: dict[str, Any] = {"model": self._model, "input": text}
            # Many non-OpenAI API gateways return 400 if 'dimensions' is passed
            resp = self._client.embeddings.create(**kwargs)
            raw_vec = resp.data[0].embedding
            norm_vec = self._normalize(raw_vec)
        except Exception as exc:
            if isinstance(exc, NotImplementedError):
                logger.info("Remote embedding skipped (%s). Using fallback deterministic vector.", exc)
            else:
                logger.warning("Remote embedding API call failed (%s). Using fallback deterministic vector.", exc)
            norm_vec = _hash_embed(text, self.dim)

        _EMBEDDING_CACHE[cache_key] = norm_vec
        return norm_vec

    @retry_with_backoff(max_retries=3, initial_delay=0.5)
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        
        results: list[list[float] | None] = [None] * len(texts)
        missing_indices: list[int] = []
        missing_texts: list[str] = []

        for idx, text in enumerate(texts):
            cache_key = _get_text_hash(text, self.dim)
            if cache_key in _EMBEDDING_CACHE:
                results[idx] = _EMBEDDING_CACHE[cache_key]
            else:
                missing_indices.append(idx)
                missing_texts.append(text)

        if missing_texts:
            try:
                if "api.groq.com" in str(self._client.base_url).lower():
                    raise NotImplementedError("Groq does not support embeddings API.")

                kwargs: dict[str, Any] = {"model": self._model, "input": missing_texts}
                resp = self._client.embeddings.create(**kwargs)
                for m_idx, item in zip(missing_indices, resp.data):
                    norm_vec = self._normalize(item.embedding)
                    cache_key = _get_text_hash(texts[m_idx], self.dim)
                    _EMBEDDING_CACHE[cache_key] = norm_vec
                    results[m_idx] = norm_vec
            except Exception as exc:
                if isinstance(exc, NotImplementedError):
                    logger.info("Remote embed_batch skipped (%s). Using fallback deterministic vectors.", exc)
                else:
                    logger.warning("Remote embed_batch API call failed (%s). Using fallback deterministic vectors.", exc)
                for m_idx in missing_indices:
                    norm_vec = _hash_embed(texts[m_idx], self.dim)
                    cache_key = _get_text_hash(texts[m_idx], self.dim)
                    _EMBEDDING_CACHE[cache_key] = norm_vec
                    results[m_idx] = norm_vec

        return [res for res in results if res is not None]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def get_embedder() -> Embedder:
    settings = get_settings()
    return RemoteEmbedder(settings.embed_provider)
