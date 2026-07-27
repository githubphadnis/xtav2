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

from app.config import Settings, get_settings
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

_STRUCTURE_SYSTEM = """You extract expense fields from a retail receipt image or OCR text.
Return ONLY a JSON object with these keys:
  amount (number), currency (3-letter ISO, usually EUR),
  merchant (store name), category (one short English word),
  spent_on (YYYY-MM-DD), note (short string or null),
  items (array of purchased products).

Each items[] entry:
  {"description": "product name as printed", "quantity": number or null, "amount": line total}

Rules:
- amount = final TOTAL to pay (German: SUMME, Summe EUR, Gesamtbetrag).
  Never use PAYBACK points, Steuernummer, PLZ, or a single line as the header amount unless it is the total.
- German decimals use comma: 19,32 → 19.32
- spent_on = receipt date. German DD.MM.YY or DD.MM.YYYY.
  Example: 25.07.26 → 2026-07-25. Never invent a year.
- merchant = store name near the top (REWE, Edeka), not a product.
- category = ONE of: groceries, restaurant, fuel, pharmacy, household, other.
- items = every purchasable product line with its price. Skip MwSt/VAT blocks,
  PAYBACK, payment method, change, card slips, and the SUMME/total row itself.
- If a field is unreadable, use null / []. Do not hallucinate products.
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


def _coerce_items(raw: object, currency: str) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        return []
    skip_words = (
        "summe",
        "total",
        "gesamt",
        "mwst",
        "payback",
        "karte",
        "bar",
        "gegeben",
        "zurück",
        "wechselgeld",
        "steuernummer",
    )
    out: list[dict[str, object]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        desc = str(entry.get("description") or entry.get("name") or "").strip()
        if not desc or len(desc) < 2:
            continue
        if any(ch in desc for ch in "[]{}"):
            continue
        lowered = desc.lower()
        if any(w in lowered for w in skip_words):
            continue
        try:
            amount = Decimal(str(entry.get("amount") or entry.get("price") or "0").replace(",", "."))
        except (InvalidOperation, ValueError):
            continue
        if amount <= 0:
            continue
        qty: Decimal | None = None
        if entry.get("quantity") is not None:
            try:
                qty = Decimal(str(entry["quantity"]).replace(",", "."))
            except (InvalidOperation, ValueError):
                qty = None
        out.append(
            {
                "description": desc[:512],
                "quantity": qty,
                "amount": amount,
                "currency": currency,
            }
        )
    return out[:80]


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
    items = _coerce_items(raw.get("items"), currency)
    return {
        "amount": amount,
        "currency": currency or settings.base_currency.upper(),
        "merchant": _sanitize_merchant(raw.get("merchant")),
        "category": _sanitize_category(raw.get("category")),
        "spent_on": _parse_spent_on(raw.get("spent_on"), today),
        "note": note[:255],
        "items": items,
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
        "category, spent_on, note, and items[] product lines. Return JSON only."
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
    """Try OCR providers. Google text first when allowed; local vision fallback."""
    errors: list[str] = []

    if google_ok:
        try:
            text = await extract_text_via_google_vision(
                settings, image_bytes=image_bytes, privacy_on=privacy_on
            )
            raw = await structure_text_with_ollama(settings, text=text)
            return raw, None, "google_vision+ollama_structure"
        except (RuntimeError, httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Google Vision OCR failed: %s", exc)
            errors.append(str(exc))

    if settings.ollama_vision_allowed():
        try:
            raw = await extract_via_ollama_vision(
                settings, image_bytes=image_bytes, content_type=content_type
            )
            return raw, None, "ollama_vision"
        except (RuntimeError, httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Ollama vision OCR failed: %s", exc)
            errors.append(str(exc))

    if settings.feature_ocr_google_vision and privacy_on:
        return None, "Google Vision blocked by privacy local-only", "none"
    if errors:
        return None, "; ".join(errors), "none"
    return None, "OCR providers off — fill fields manually", "none"


async def create_pending_from_upload(
    db: Session,
    *,
    settings: Settings,
    data: bytes,
    content_type: str,
    filename: str | None,
) -> tuple[Expense, str | None]:
    """Legacy sync path: save + OCR + pending in one call (tests / tooling)."""
    row = enqueue_receipt_upload(
        db,
        settings=settings,
        data=data,
        content_type=content_type,
        filename=filename,
    )
    warning = await finalize_receipt_ocr(expense_id=row.id)
    # Re-load after finalize
    db.refresh(row)
    return row, warning


def enqueue_receipt_upload(
    db: Session,
    *,
    settings: Settings,
    data: bytes,
    content_type: str,
    filename: str | None,
) -> Expense:
    """Save image and create a processing row — no OCR yet (fast path for Capture)."""
    relative = save_receipt_bytes(
        settings, data=data, content_type=content_type, filename=filename
    )
    today = datetime.now(ZoneInfo(settings.app_timezone)).date()
    return expense_service.add_expense(
        db,
        settings=settings,
        spent_on=today,
        amount=Decimal("0.00"),
        currency=settings.base_currency.upper(),
        merchant="",
        category="receipt",
        note="ocr:queued",
        source="receipt",
        status="processing",
        receipt_path=relative,
    )


async def finalize_receipt_ocr(*, expense_id: int) -> str | None:
    """Run OCR for a processing expense and flip it to pending. Safe to retry."""
    from app.db import get_session_factory

    settings = get_settings()
    SessionLocal = get_session_factory()

    with SessionLocal() as db:
        row = db.get(Expense, expense_id)
        if row is None:
            return "Expense not found"
        if row.status != "processing":
            return None
        if not row.receipt_path:
            expense_service.update_expense(
                db,
                settings=settings,
                expense_id=expense_id,
                spent_on=row.spent_on,
                amount=row.amount,
                currency=row.currency,
                merchant=row.merchant,
                category=row.category,
                note="ocr:missing_file",
                status="pending",
            )
            return "Missing receipt file"
        path = upload_root(settings) / row.receipt_path
        if not path.is_file():
            expense_service.update_expense(
                db,
                settings=settings,
                expense_id=expense_id,
                spent_on=row.spent_on,
                amount=row.amount,
                currency=row.currency,
                merchant=row.merchant,
                category=row.category,
                note="ocr:missing_file",
                status="pending",
            )
            return "Missing receipt file"
        data = path.read_bytes()
        suffix = path.suffix.lower()
        content_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".heic": "image/heic",
        }.get(suffix, "image/jpeg")
        privacy_on = settings_store.privacy_local_only(db, settings)
        google_ok = settings_store.google_vision_allowed(db, settings)

    today = datetime.now(ZoneInfo(settings.app_timezone)).date()
    fields: dict[str, object] = {
        "amount": Decimal("0.00"),
        "currency": settings.base_currency.upper(),
        "merchant": "",
        "category": "receipt",
        "spent_on": today,
        "note": "",
        "items": [],
    }
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
    if warning and not fields.get("note"):
        fields["note"] = f"ocr:skipped:{warning[:200]}"
    elif warning:
        fields["note"] = f"{fields['note']}; {warning}"[:255]

    with SessionLocal() as db:
        row = db.get(Expense, expense_id)
        if row is None or row.status != "processing":
            return warning
        expense_service.update_expense(
            db,
            settings=settings,
            expense_id=expense_id,
            spent_on=fields["spent_on"],  # type: ignore[arg-type]
            amount=fields["amount"],  # type: ignore[arg-type]
            currency=str(fields["currency"]),
            merchant=str(fields["merchant"]),
            category=str(fields["category"]),
            note=str(fields["note"]),
            status="pending",
        )
        items = fields.get("items") or []
        if settings.feature_line_items and isinstance(items, list) and items:
            expense_service.replace_line_items(
                db,
                expense_id=expense_id,
                items=items,  # type: ignore[arg-type]
                currency=str(fields["currency"]),
            )
    return warning
