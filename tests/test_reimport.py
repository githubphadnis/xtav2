"""Tests for wipe + reimport from existing upload files (#24)."""

from __future__ import annotations

import os
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_RECEIPT_OCR"] = "true"
os.environ["FEATURE_OCR_OLLAMA_VISION"] = "false"
os.environ["FEATURE_OCR_GOOGLE_VISION"] = "false"
os.environ["PRIVACY_LOCAL_ONLY"] = "true"
os.environ["GOOGLE_VISION_API_KEY"] = ""
os.environ["FEATURE_LINE_ITEMS"] = "true"

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.services import expenses as expense_service
from app.services.reimport import (
    enqueue_existing_receipt,
    list_receipt_images,
    reimport_receipts,
    wipe_all_expenses,
)

_tmp_upload: tempfile.TemporaryDirectory[str] | None = None


def setup_function() -> None:
    global _tmp_upload
    if _tmp_upload is not None:
        _tmp_upload.cleanup()
    _tmp_upload = tempfile.TemporaryDirectory(prefix="xtav2-reimport-")
    os.environ["UPLOAD_DIR"] = _tmp_upload.name
    get_settings.cache_clear()
    from app import db as db_mod

    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()


def teardown_function() -> None:
    global _tmp_upload
    if _tmp_upload is not None:
        _tmp_upload.cleanup()
        _tmp_upload = None


def test_list_and_enqueue_existing_without_copy() -> None:
    settings = get_settings()
    root = Path(settings.upload_dir)
    name = "kept_receipt.jpg"
    (root / name).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)

    assert list_receipt_images(settings) == [name]

    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        row = enqueue_existing_receipt(db, settings=settings, relative_path=name)
        assert row.status == "processing"
        assert row.receipt_path == name
        assert row.note == "ocr:reimport"
        assert (root / name).is_file()


def test_wipe_and_reimport_dry_run_then_wipe() -> None:
    import asyncio

    settings = get_settings()
    root = Path(settings.upload_dir)
    (root / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16)
    (root / "b.png").write_bytes(b"\x89PNG" + b"\x00" * 16)
    (root / "notes.txt").write_text("ignore", encoding="utf-8")

    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 1),
            amount=Decimal("10.00"),
            currency="EUR",
            merchant="Old",
            category="misc",
            status="posted",
        )
        dry = asyncio.run(
            reimport_receipts(db, settings=settings, wipe=True, run_ocr=False, dry_run=True)
        )
        assert dry.files_found == 2
        assert dry.enqueued == 0
        assert expense_service.count_expenses(db, status="posted") == 1

        wiped = wipe_all_expenses(db)
        assert wiped == 1
        assert expense_service.count_expenses(db, status="posted") == 0
        assert expense_service.count_expenses(db, status="pending") == 0
        assert expense_service.count_expenses(db, status="processing") == 0

        result = asyncio.run(
            reimport_receipts(db, settings=settings, wipe=False, run_ocr=True, dry_run=False)
        )
        assert result.files_found == 2
        assert result.enqueued == 2
        assert result.ocr_done == 2
        pending = expense_service.list_pending(db)
        assert len(pending) == 2
        assert all(p.receipt_path in {"a.jpg", "b.png"} for p in pending)
        assert (root / "a.jpg").is_file()
        assert (root / "b.png").is_file()
