"""Receipt capture + optional vision extraction."""

from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations.ollama import list_models
from app.models import Expense
from app.services import expenses as expense_service

logger = logging.getLogger("xtav2.receipts")

_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
}


def upload_root(settings: Settings) -> Path:
    root = Path(settings.upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_receipt_bytes(
    settings: Settings, *, data: bytes, content_type: str, filename: str | None
) -> str:
    """Persist upload bytes; return relative path under upload_dir."""
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_size_mb}MB limit")
    ext = _IMAGE_TYPES.get((content_type or "").lower())
    if not ext and filename:
        suffix = Path(filename).suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
            ext = ".jpg" if suffix == ".jpeg" else suffix
    if not ext:
        raise ValueError("Unsupported file type — use JPEG, PNG, or WebP")
    name = f"{datetime.now(tz=ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    path = upload_root(settings) / name
    path.write_bytes(data)
    return name


async def extract_receipt_fields(
    settings: Settings, *, image_bytes: bytes, content_type: str
) -> dict[str, object]:
    """Call Ollama vision model for structured receipt fields (best-effort)."""
    model = (settings.ollama_vision_model or "").strip()
    if not model:
        raise RuntimeError(
            "OLLAMA_VISION_MODEL is empty. Set it to a vision-capable model from "
            "`ollama list` on lenai, or disable FEATURE_OCR_OLLAMA_VISION."
        )
    available = await list_models(settings)
    if available and not any(m == model or m.startswith(f"{model}:") for m in available):
        raise RuntimeError(
            f"Vision model '{model}' not on lenai. Available: {', '.join(available)}. "
            "Pull a vision model or turn off FEATURE_OCR_OLLAMA_VISION."
        )

    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime = content_type if content_type in _IMAGE_TYPES else "image/jpeg"
    data_url = f"data:{mime};base64,{b64}"
    system = (
        "Extract expense fields from the receipt image. Return JSON only with keys: "
        "amount (number), currency (3-letter), merchant (string), category (string), "
        "spent_on (YYYY-MM-DD), note (string). Use null when unknown."
    )
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": "Read this receipt and extract the fields.",
                "images": [data_url],
            },
        ],
    }
    # Ollama chat API expects images as raw base64 in some versions — try both shapes.
    payload_alt = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": "Read this receipt and extract the fields.",
                "images": [b64],
            },
        ],
    }
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    timeout = httpx.Timeout(settings.ollama_vision_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload_alt)
        if response.status_code >= 400:
            response = await client.post(url, json=payload)
        response.raise_for_status()
        content = (response.json().get("message") or {}).get("content") or "{}"
    return _parse_extract_json(content)


def _parse_extract_json(content: str) -> dict[str, object]:
    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return {}
        try:
            raw = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def _coerce_extract(
    settings: Settings, raw: dict[str, object], today: date
) -> dict[str, object]:
    amount = Decimal("0.00")
    if raw.get("amount") is not None:
        try:
            amount = Decimal(str(raw["amount"]))
        except (InvalidOperation, ValueError):
            amount = Decimal("0.00")
    currency = str(raw.get("currency") or settings.base_currency).strip().upper()[:3]
    spent_on = today
    if raw.get("spent_on"):
        try:
            spent_on = date.fromisoformat(str(raw["spent_on"])[:10])
        except ValueError:
            spent_on = today
    return {
        "amount": amount,
        "currency": currency or settings.base_currency.upper(),
        "merchant": str(raw.get("merchant") or "").strip(),
        "category": str(raw.get("category") or "receipt").strip() or "receipt",
        "spent_on": spent_on,
        "note": str(raw.get("note") or "").strip(),
    }


async def create_pending_from_upload(
    db: Session,
    *,
    settings: Settings,
    data: bytes,
    content_type: str,
    filename: str | None,
) -> tuple[Expense, str | None]:
    """Save image, optionally OCR, create pending expense. Returns (row, warning)."""
    relative = save_receipt_bytes(
        settings, data=data, content_type=content_type, filename=filename
    )
    today = datetime.now(ZoneInfo(settings.app_timezone)).date()
    fields: dict[str, object] = {
        "amount": Decimal("0.00"),
        "currency": settings.base_currency.upper(),
        "merchant": "",
        "category": "receipt",
        "spent_on": today,
        "note": "",
    }
    warning: str | None = None
    if settings.feature_ocr_ollama_vision:
        try:
            raw = await extract_receipt_fields(
                settings, image_bytes=data, content_type=content_type
            )
            fields = _coerce_extract(settings, raw, today)
        except (RuntimeError, httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Vision OCR failed: %s", exc)
            warning = str(exc)

    row = expense_service.add_expense(
        db,
        settings=settings,
        spent_on=fields["spent_on"],  # type: ignore[arg-type]
        amount=fields["amount"],  # type: ignore[arg-type]
        currency=str(fields["currency"]),
        merchant=str(fields["merchant"]),
        category=str(fields["category"]),
        note=str(fields["note"]),
        source="receipt",
        status="pending",
        receipt_path=relative,
    )
    return row, warning
