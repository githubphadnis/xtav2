"""Ollama client for spend Q&A (FEATURE_OLLAMA_QA)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger("xtav2.ollama")


async def list_models(settings: Settings) -> list[str]:
    """Return model names from GET /api/tags (empty on failure)."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            models = response.json().get("models") or []
            return [str(m.get("name") or m.get("model") or "") for m in models if m]
    except httpx.HTTPError as exc:
        logger.warning("Ollama /api/tags failed: %s", exc)
        return []


async def ask_ollama(settings: Settings, prompt: str, system: str) -> str:
    """Call Ollama chat API; raise with an actionable message on failure."""
    base = settings.ollama_base_url.rstrip("/")
    url = f"{base}/api/chat"
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
        if response.status_code == 404:
            available = await list_models(settings)
            hint = (
                f" Available on lenai: {', '.join(available)}."
                if available
                else " Could not list models via /api/tags."
            )
            raise RuntimeError(
                f"Ollama 404 for model '{settings.ollama_model}' at {url}.{hint} "
                "Set OLLAMA_MODEL in Portainer to a name from `ollama list` on lenai."
            )
        response.raise_for_status()
        data = response.json()
    message = data.get("message") or {}
    content = message.get("content") or ""
    if not content:
        logger.warning("Ollama returned empty content")
    return str(content)
