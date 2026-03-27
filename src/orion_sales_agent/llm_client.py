"""Small HTTP client wrapper for LLM chat-completions calls."""
from __future__ import annotations

import httpx

from .config import settings


def llm_enabled() -> bool:
    """Return True if an LLM API key is configured."""

    return bool(settings.llm_api_key.strip())


def llm_chat(system_prompt: str, user_prompt: str) -> str:
    """Call configured chat-completions endpoint and return text response."""

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
    with httpx.Client(timeout=30) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]
