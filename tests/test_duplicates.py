"""Duplicate detection tests."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_MULTI_CURRENCY"] = "true"
os.environ["FEATURE_RECEIPT_OCR"] = "false"
os.environ["FEATURE_OCR_GOOGLE_VISION"] = "false"
os.environ["PRIVACY_LOCAL_ONLY"] = "true"
os.environ["GOOGLE_VISION_API_KEY"] = ""
os.environ["BASE_CURRENCY"] = "EUR"

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.services import expenses as expense_service
from app.services.duplicates import (
    compute_fingerprint,
    count_active_duplicates,
    dismiss_duplicate,
    normalize_merchant,
)

get_settings.cache_clear()


def setup_function() -> None:
    get_settings.cache_clear()
    from app import db as db_mod

    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()


def test_normalize_merchant() -> None:
    assert normalize_merchant("EDEKA GmbH & Co. KG") == "edeka"


def test_fingerprint_requires_merchant_or_items() -> None:
    assert (
        compute_fingerprint(
            spent_on=date(2026, 7, 1), amount=Decimal("10.00"), merchant=""
        )
        is None
    )
    fp = compute_fingerprint(
        spent_on=date(2026, 7, 1), amount=Decimal("10.00"), merchant="Edeka"
    )
    assert fp is not None


def test_duplicate_flagged_and_excluded_from_ask() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        a = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 10),
            amount=Decimal("19.32"),
            currency="EUR",
            merchant="EDEKA",
            category="groceries",
            status="posted",
        )
        b = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 10),
            amount=Decimal("19.32"),
            currency="EUR",
            merchant="Edeka GmbH",
            category="groceries",
            status="posted",
        )
        assert a.duplicate_of_id is None
        assert b.duplicate_of_id == a.id
        assert count_active_duplicates(db) == 1

        spend = expense_service.query_spend(db, settings=settings)
        assert spend["count"] == 1
        assert spend["total"] == 19.32

        dismiss_duplicate(db, expense_id=b.id)
        spend2 = expense_service.query_spend(db, settings=settings)
        assert spend2["count"] == 2
        assert spend2["total"] == 38.64


def test_different_amount_not_duplicate() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 10),
            amount=Decimal("10.00"),
            currency="EUR",
            merchant="REWE",
            status="posted",
        )
        b = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 10),
            amount=Decimal("11.00"),
            currency="EUR",
            merchant="REWE",
            status="posted",
        )
        assert b.duplicate_of_id is None
        assert expense_service.query_spend(db, settings=settings)["count"] == 2
