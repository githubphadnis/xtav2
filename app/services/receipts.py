"""Receipt capture + OCR providers (local vision / Google Vision / manual)."""

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
from app.integrations.ollama import ask_ollama, list_models
from app.models import Expense
from app.services import expenses as expense_service
from app.services import settings_store

logger = logging.getLogger("xtav2.receipts")

_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
}

_STRUCTURE_SYSTEM = """You extract expense fields from a retail receipt image or text.
Return ONLY a JSON object with these keys:
  amount (number, e.g. 19.32), currency (3-letter ISO, usually EUR),
  merchant (store name string), category (one short English word),
  spent_on (YYYY-MM-DD), note (short string or null).

Rules:
- amount = the final TOTAL to pay (German: SUMME, Summe EUR, Gesamtbetrag, Bar, Karte).
  Never use PAYBACK points, Steuernummer, PLZ, or line-item prices as amount.
- German decimals use comma: 19,32 → 19.32
- spent_on = receipt date. German format DD.MM.YY or DD.MM.YYYY.
  Example: 25.07.26 → 2026-07-25 (21st century). Never invent a year.
- merchant = store / company name printed near the top (e.g. REWE, Edeka), not a product.
- category = ONE of: groceries, restaurant, fuel, pharmacy, household, other.
  Never put product names, brands, or list syntax in category.
- If a field is unreadable, use null. Do not hallucinate.
"""

_CATEGORY_ALLOW = {
    "groceries",
    "grocery",
    "food",
    "restaurant",
    "dining",
    "fuel",
    "gas",
    "petrol",
    "pharmacy",
    "chemist",
    "household",
    "other",
    "receipt",
    "shopping",
    "transport",
    "travel",
    "entertainment",
    "health",
}

_DE_DATE = re.compile(
    r"\b(\d{1,2})[./](\d{1,2})[./](\d{2}|\d{4})\b"
)


def _parse_spent_on(value: object, today: date) -> date:
    """Parse ISO or German dates; reject absurd years relative to today."""
    if value is None:
        return today
    text = str(value).strip()
    parsed: date | None = None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text[:10]):
        try:
            parsed = date.fromisoformat(text[:10])
        except ValueError:
            parsed = None
    if parsed is None:
        match = _DE_DATE.search(text)
        if match:
            day, month, year_s = match.groups()
            year = int(year_s)
            if year < 100:
                year += 2000
            try:
                parsed = date(year, int(month), int(day))
            except ValueError:
                parsed = None
    if parsed is None:
        return today
    # Reject dates more than ~2 years from today (model year hallucinations).
    if abs((parsed - today).days) > 730:
        return today
    return parsed


def _sanitize_category(raw: object) -> str:
    text = str(raw or "").strip()
    if not text:
        return "receipt"
    # Reject list/JSON debris and product-line junk (e.g. "['HERZ ASSASSIN").
    if any(ch in text for ch in "[]{}'\""):
        return "receipt"
    if len(text) > 40 or "," in text or "\n" in text:
        return "receipt"
    lowered = text.lower()
    if lowered in _CATEGORY_ALLOW:
        if lowered in {"grocery", "food", "shopping"}:
            return "groceries"
        if lowered in {"dining"}:
            return "restaurant"
        if lowered in {"gas", "petrol"}:
            return "fuel"
        if lowered in {"chemist", "health"}:
            return "pharmacy"
        return lowered
    # Unknown short token — keep if it looks like a plain word
    if re.fullmatch(r"[A-Za-z][A-Za-z -]{0,24}", text):
        return text.lower()
    return "receipt"


def _sanitize_merchant(raw: object) -> str:
    text = str(raw or "").strip()
    if not text or any(ch in text for ch in "[]{}"):
        return ""
    # Drop trailing legal noise length if absurdly long
    return text[:120]


def _coerce_extract(
    settings: Settings, raw: dict[str, object], today: date
) -> dict[str, object]:
    amount = Decimal("0.00")
    if raw.get("amount") is not None:
        try:
            amount = Decimal(str(raw["amount"]).replace(",", "."))
        except (InvalidOperation, ValueError):
            amount = Decimal("0.00")
    if amount < 0:
        amount = Decimal("0.00")
    currency = str(raw.get("currency") or settings.base_currency).strip().upper()[:3]
    if not re.fullmatch(r"[A-Z]{3}", currency):
        currency = settings.base_currency.upper()
    note = str(raw.get("note") or "").strip()
    if note.upper() in {"SUMME", "TOTAL", "GESAMTBETRAG", "NULL"}:
        note = ""
    return {
        "amount": amount,
        "currency": currency or settings.base_currency.upper(),
        "merchant": _sanitize_merchant(raw.get("merchant")),
        "category": _sanitize_category(raw.get("category")),
        "spent_on": _parse_spent_on(raw.get("spent_on"), today),
        "note": note[:255],
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


async def extract_via_ollama_vision(
    settings: Settings, *, image_bytes: bytes, content_type: str
) -> dict[str, object]:
    """Call Ollama vision model for structured receipt fields."""
    model = (settings.ollama_vision_model or "").strip()
    if not model:
        raise RuntimeError("OLLAMA_VISION_MODEL is empty")
    available = await list_models(settings)
    if available and not any(m == model or m.startswith(f"{model}:") for m in available):
        raise RuntimeError(
            f"Vision model '{model}' not on lenai. Available: {', '.join(available)}"
        )

    today = datetime.now(ZoneInfo(settings.app_timezone)).date()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    user_prompt = (
        f"Today's date is {today.isoformat()}. "
        "Read the receipt image. Extract amount (SUMME/total), currency, merchant, "
        "category, spent_on, note. Return JSON only."
    )
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
        "messages": [
            {"role": "system", "content": _STRUCTURE_SYSTEM},
            {
                "role": "user",
                "content": user_prompt,
                "images": [b64],
            },
        ],
    }
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    timeout = httpx.Timeout(settings.ollama_vision_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        content = (response.json().get("message") or {}).get("content") or "{}"
    return _parse_extract_json(content)


async def extract_text_via_google_vision(
    settings: Settings, *, image_bytes: bytes, privacy_on: bool
) -> str:
    """OCR raw text via Google Cloud Vision REST API (DOCUMENT_TEXT_DETECTION)."""
    if privacy_on:
        raise RuntimeError("Privacy local-only blocks Google Vision")
    key = settings.google_vision_api_key.strip()
    if not key:
        raise RuntimeError("GOOGLE_VISION_API_KEY is empty")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    url = f"https://vision.googleapis.com/v1/images:annotate?key={key}"
    payload = {
        "requests": [
            {
                "image": {"content": b64},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    responses = data.get("responses") or [{}]
    annotation = responses[0].get("fullTextAnnotation") or {}
    text = annotation.get("text") or ""
    if not text:
        # Fallback to first textAnnotations entry
        anns = responses[0].get("textAnnotations") or []
        if anns:
            text = str(anns[0].get("description") or "")
    if not text.strip():
        raise RuntimeError("Google Vision returned no text")
    return text


async def structure_text_with_ollama(settings: Settings, *, text: str) -> dict[str, object]:
    """Turn OCR text into expense JSON using the local chat model."""
    today = datetime.now(ZoneInfo(settings.app_timezone)).date()
    prompt = (
        f"Today's date is {today.isoformat()}.\n"
        f"Receipt text:\n{text[:6000]}\n\nReturn JSON only."
    )
    content = await ask_ollama(settings, prompt, _STRUCTURE_SYSTEM)
    return _parse_extract_json(content)


async def run_ocr_pipeline(
    settings: Settings,
    *,
    image_bytes: bytes,
    content_type: str,
    privacy_on: bool,
    google_ok: bool,
) -> tuple[dict[str, object] | None, str | None, str]:
    """Try configured OCR providers. Returns (raw_fields, warning, provider_used)."""
    ollama_err: str | None = None
    if settings.ollama_vision_allowed():
        try:
            raw = await extract_via_ollama_vision(
                settings, image_bytes=image_bytes, content_type=content_type
            )
            return raw, None, "ollama_vision"
        except (RuntimeError, httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Ollama vision OCR failed: %s", exc)
            ollama_err = str(exc)

    if google_ok:
        try:
            text = await extract_text_via_google_vision(
                settings, image_bytes=image_bytes, privacy_on=privacy_on
            )
            raw = await structure_text_with_ollama(settings, text=text)
            return raw, None, "google_vision+ollama_structure"
        except (RuntimeError, httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Google Vision OCR failed: %s", exc)
            parts = [p for p in (ollama_err, str(exc)) if p]
            return None, "; ".join(parts) if parts else str(exc), "none"

    if settings.feature_ocr_google_vision and privacy_on:
        return None, "Google Vision blocked by privacy local-only", "none"
    if ollama_err:
        return None, ollama_err, "none"
    return None, "OCR providers off — fill fields manually", "none"


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
    privacy_on = settings_store.privacy_local_only(db, settings)
    google_ok = settings_store.google_vision_allowed(db, settings)
    raw, warning, provider = await run_ocr_pipeline(
        settings,
        image_bytes=data,
        content_type=content_type,
        privacy_on=privacy_on,
        google_ok=google_ok,
    )
    if raw:
        fields = _coerce_extract(settings, raw, today)
        if provider and not fields.get("note"):
            fields["note"] = f"ocr:{provider}"

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
