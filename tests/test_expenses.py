"""Expense service tests (SQLite in-memory)."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

# Configure before app imports resolve settings/engine.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_MULTI_CURRENCY"] = "true"
os.environ["BASE_CURRENCY"] = "EUR"

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.features import flag_snapshot
from app.services import expenses as expense_service

get_settings.cache_clear()


def setup_function() -> None:
    get_settings.cache_clear()
    from app import db as db_mod

    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()


def test_flag_snapshot_defaults() -> None:
    flags = flag_snapshot(get_settings())
    assert flags["FEATURE_MANUAL_ENTRY"] is True
    assert flags["FEATURE_RECEIPT_OCR"] is False


def test_add_and_query_spend() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 1),
            amount=Decimal("3.50"),
            currency="EUR",
            merchant="REWE",
            category="groceries",
            note="crisps",
        )
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 2),
            amount=Decimal("12.00"),
            currency="EUR",
            merchant="REWE",
            category="groceries",
            note="milk",
        )
        result = expense_service.query_spend(db, settings=settings, q="crisps")
        assert result["count"] == 1
        assert result["total"] == 3.5

        nl = expense_service.query_spend(
            db, settings=settings, q="How much did I spend at REWE this year?"
        )
        assert nl["count"] == 2
        assert nl["total"] == 15.5
        assert "REWE" in nl["tokens"]


def test_format_money() -> None:
    assert expense_service.format_money(Decimal("200.0000")) == "200.00"
    assert expense_service.format_money("3.5") == "3.50"
