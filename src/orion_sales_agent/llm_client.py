"""Small HTTP client wrapper for LLM chat-completions calls.

Includes a simple exponential-backoff retry loop (circuit breaker lite) that
retries transient HTTP 429/5xx failures up to ``LLM_MAX_RETRIES`` times with
jittered sleep, using only stdlib primitives — no extra dependencies.
"""
from __future__ import annotations

import logging
import random
import time

import httpx

from .config import settings

logger = logging.getLogger(__name__)

# Retry configuration — uses stdlib only, no extra deps.
_LLM_MAX_RETRIES: int = 3
_LLM_RETRY_BASE_DELAY: float = 1.0   # seconds; doubled on each attempt
_LLM_RETRYABLE_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})


def llm_enabled() -> bool:
    """Return True if an LLM API key is configured."""

    return bool(settings.llm_api_key.strip())


def _is_retryable(exc: Exception) -> bool:
    """Return True for transient HTTP errors worth retrying."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _LLM_RETRYABLE_STATUS
    if isinstance(exc, httpx.ConnectError | httpx.TimeoutException | httpx.RemoteProtocolError):
        return True
    return False


def llm_chat(system_prompt: str, user_prompt: str) -> str:
    """Call configured chat-completions endpoint and return text response.

    Retries up to ``_LLM_MAX_RETRIES`` times on transient failures using
    full-jitter exponential backoff.  Non-retryable errors propagate immediately.
    """

    if not llm_enabled():
        raise RuntimeError("LLM not configured")

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"

    last_exc: Exception | None = None
    for attempt in range(_LLM_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=settings.llm_timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                data_desc = list(data) if isinstance(data, dict) else type(data).__name__
                raise RuntimeError(
                    f"Unexpected LLM response structure: {exc}. Response keys: {data_desc}"
                ) from exc
            if not isinstance(content, str):
                raise RuntimeError(
                    f"LLM response content is not a string: {type(content).__name__}"
                )
            return content

        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= _LLM_MAX_RETRIES or not _is_retryable(exc):
                raise
            # Full-jitter exponential backoff: sleep up to base * 2^attempt seconds
            cap = _LLM_RETRY_BASE_DELAY * (2 ** attempt)
            delay = random.uniform(0, cap)
            logger.warning(
                "LLM call failed (attempt %d/%d), retrying in %.2fs: %s",
                attempt + 1, _LLM_MAX_RETRIES, delay, exc,
            )
            time.sleep(delay)

    # Should be unreachable, but satisfy type checker
    raise RuntimeError("LLM call failed after all retries") from last_exc
