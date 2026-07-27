"""Receipt capture service tests."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_RECEIPT_OCR"] = "true"
os.environ["FEATURE_OCR_OLLAMA_VISION"] = "false"
os.environ["FEATURE_OCR_GOOGLE_VISION"] = "false"
os.environ["PRIVACY_LOCAL_ONLY"] = "true"
os.environ["GOOGLE_VISION_API_KEY"] = ""
os.environ["UPLOAD_DIR"] = "uploads-test"

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.services import expenses as expense_service
from app.services.receipts import create_pending_from_upload, save_receipt_bytes

get_settings.cache_clear()


def setup_function() -> None:
    os.environ["FEATURE_OCR_GOOGLE_VISION"] = "false"
    os.environ["PRIVACY_LOCAL_ONLY"] = "true"
    os.environ["GOOGLE_VISION_API_KEY"] = ""
    get_settings.cache_clear()
    from app import db as db_mod

    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()
    Path("uploads-test").mkdir(exist_ok=True)


def test_save_and_pending_receipt_without_vision() -> None:
    import asyncio

    settings = get_settings()
    SessionLocal = get_session_factory()
    # Minimal JPEG header bytes are enough for storage; content-type drives extension.
    data = b"\xff\xd8\xff\xe0" + b"\x00" * 64

    async def _run():
        with SessionLocal() as db:
            row, warning = await create_pending_from_upload(
                db,
                settings=settings,
                data=data,
                content_type="image/jpeg",
                filename="receipt.jpg",
            )
            assert warning  # OCR off → manual fill message
            assert "OCR" in warning or "manual" in warning.lower()
            assert row.status == "pending"
            assert row.source == "receipt"
            assert row.receipt_path
            assert (Path(settings.upload_dir) / row.receipt_path).is_file()
            pending = expense_service.list_pending(db)
            assert len(pending) == 1
            posted = expense_service.list_expenses(db, status="posted")
            assert posted == []
            confirmed = expense_service.update_expense(
                db,
                settings=settings,
                expense_id=row.id,
                spent_on=date(2026, 7, 26),
                amount=Decimal("12.50"),
                currency="EUR",
                merchant="REWE",
                category="groceries",
                note="milk",
                status="posted",
            )
            assert confirmed is not None
            assert confirmed.status == "posted"
            assert expense_service.list_pending(db) == []
            assert expense_service.query_spend(db, settings=settings)["total"] == 12.5

    asyncio.run(_run())


def test_reject_oversized_upload() -> None:
    settings = get_settings()
    settings.max_upload_size_mb = 0  # force tiny limit via object — settings is cached
    # Re-read via env for clarity in a fresh settings object is hard with cache;
    # call save with huge payload against MB=10 default and skip — use direct ValueError path:
    from app.config import Settings

    tiny = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        upload_dir="uploads-test",
        max_upload_size_mb=0,
    )
    try:
        save_receipt_bytes(tiny, data=b"abc", content_type="image/jpeg", filename="a.jpg")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_coerce_sanitizes_bad_vision_fields() -> None:
    from app.config import Settings
    from app.services.receipts import _coerce_extract

    settings = Settings(base_currency="EUR")
    today = date(2026, 7, 26)
    # LLM invents absurd year; OCR text has the real printed date — OCR must win.
    out = _coerce_extract(
        settings,
        {
            "amount": "19,32",
            "currency": "EUR",
            "merchant": "REWE",
            "category": "['HERZ ASSASSIN",
            "spent_on": "2016-08-30",
            "note": "SUMME",
            "items": [
                {"description": "Schokolade", "amount": "1,29"},
                {"description": "SUMME", "amount": "19,32"},
                {"description": "['JUNK", "amount": "1.00"},
            ],
        },
        today,
        ocr_text="REWE\nDatum: 15.03.26\nSUMME EUR 19,32\n",
    )
    assert out["amount"] == Decimal("19.32")
    assert out["category"] == "receipt"
    assert out["spent_on"] == date(2026, 3, 15)
    assert out["date_source"] == "ocr"
    assert out["note"] == ""
    assert out["merchant"] == "REWE"
    assert len(out["items"]) == 1
    assert out["items"][0]["description"] == "Schokolade"

    de = _coerce_extract(
        settings,
        {"amount": 12.5, "spent_on": "25.07.26", "category": "groceries"},
        today,
    )
    assert de["spent_on"] == date(2026, 7, 25)
    assert de["category"] == "groceries"
    assert de["date_source"] == "llm"


def test_ocr_date_beats_llm_upload_day() -> None:
    """User phrase: receipt says 03.02.2026 but model returns upload day."""
    from app.config import Settings
    from app.services.receipts import _coerce_extract, extract_receipt_date_from_text

    today = date(2026, 7, 27)
    ocr = (
        "EDEKA Musterstadt\n"
        "Berliner Str. 1\n"
        "Datum 03.02.2026  Uhrzeit 18:41\n"
        "Milch 1,19\n"
        "SUMME EUR 1,19\n"
    )
    assert extract_receipt_date_from_text(ocr, today) == date(2026, 2, 3)

    settings = Settings(base_currency="EUR")
    out = _coerce_extract(
        settings,
        {
            "amount": "1.19",
            "spent_on": today.isoformat(),  # model wrongly used "today"
            "merchant": "EDEKA",
            "category": "groceries",
        },
        today,
        ocr_text=ocr,
    )
    assert out["spent_on"] == date(2026, 2, 3)
    assert out["date_source"] == "ocr"


def test_missing_date_marks_unparsed_not_silent_today_as_truth() -> None:
    from app.config import Settings
    from app.services.receipts import _coerce_extract

    settings = Settings(base_currency="EUR")
    today = date(2026, 7, 27)
    out = _coerce_extract(
        settings,
        {"amount": "5.00", "spent_on": None, "merchant": "Kiosk"},
        today,
        ocr_text="Kiosk\nSUMME 5,00\nKeine Datumzeile hier\n",
    )
    assert out["spent_on"] == today  # last resort only
    assert out["date_source"] == "fallback"
    assert "date:unparsed" in str(out["note"])


def test_async_enqueue_then_finalize() -> None:
    import asyncio

    from app.services.receipts import enqueue_receipt_upload, finalize_receipt_ocr

    settings = get_settings()
    SessionLocal = get_session_factory()
    data = b"\xff\xd8\xff\xe0" + b"\x00" * 64

    with SessionLocal() as db:
        row = enqueue_receipt_upload(
            db,
            settings=settings,
            data=data,
            content_type="image/jpeg",
            filename="fast.jpg",
        )
        assert row.status == "processing"
        assert expense_service.count_expenses(db, status="processing") == 1
        assert expense_service.list_pending(db) == []
        eid = row.id

    asyncio.run(finalize_receipt_ocr(expense_id=eid))

    with SessionLocal() as db:
        assert expense_service.count_expenses(db, status="processing") == 0
        pending = expense_service.list_pending(db)
        assert len(pending) == 1
        assert pending[0].id == eid
        assert pending[0].status == "pending"


def test_line_items_and_ask_query() -> None:
    os.environ["FEATURE_LINE_ITEMS"] = "true"
    get_settings.cache_clear()
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        row = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 25),
            amount=Decimal("19.32"),
            currency="EUR",
            merchant="REWE",
            category="groceries",
            status="posted",
        )
        expense_service.replace_line_items(
            db,
            expense_id=row.id,
            items=[
                {"description": "Schokolade Zartbitter", "amount": "1.29"},
                {"description": "Milch", "amount": "1.19"},
            ],
            currency="EUR",
        )
        result = expense_service.query_spend(
            db, settings=settings, q="How much on Schokolade?"
        )
        assert result["line_match_count"] == 1
        assert result["line_total"] == 1.29
        assert "Schokolade" in result["line_matches"][0]["description"]

        # English synonym should hit German line text.
        kebab_row = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 20),
            amount=Decimal("8.50"),
            currency="EUR",
            merchant="Imbiss",
            category="restaurant",
            status="posted",
        )
        expense_service.replace_line_items(
            db,
            expense_id=kebab_row.id,
            items=[{"description": "Döner komplett", "amount": "8.50"}],
            currency="EUR",
        )
        kebabs = expense_service.query_spend(
            db, settings=settings, q="How many times did I spend on kebabs?"
        )
        assert kebabs["line_match_count"] == 1
        assert kebabs["line_total"] == 8.5
        ans = expense_service.try_deterministic_answer(kebabs)
        assert ans is not None
        assert "8.5" in ans or "8.50" in ans
