"""Ollama client for spend Q&A (FEATURE_OLLAMA_QA)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger("xtav2.ollama")


async def ask_ollama(settings: Settings, prompt: str, system: str) -> str:
    """Call Ollama chat API; raise on transport failures."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    timeout = httpx.Timeout(settings.ollama_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    message = data.get("message") or {}
    content = message.get("content") or ""
    if not content:
        logger.warning("Ollama returned empty content")
    return str(content)
