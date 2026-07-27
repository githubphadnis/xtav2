"""Expense service tests (SQLite in-memory)."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

# Configure before app imports resolve settings/engine.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_MULTI_CURRENCY"] = "true"
os.environ["FEATURE_RECEIPT_OCR"] = "false"
os.environ["FEATURE_OCR_GOOGLE_VISION"] = "false"
os.environ["PRIVACY_LOCAL_ONLY"] = "true"
os.environ["GOOGLE_VISION_API_KEY"] = ""
os.environ["BASE_CURRENCY"] = "EUR"

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.features import flag_snapshot
from app.services import expenses as expense_service

get_settings.cache_clear()


def setup_function() -> None:
    os.environ["FEATURE_RECEIPT_OCR"] = "false"
    os.environ["FEATURE_OCR_GOOGLE_VISION"] = "false"
    os.environ["PRIVACY_LOCAL_ONLY"] = "true"
    os.environ["GOOGLE_VISION_API_KEY"] = ""
    get_settings.cache_clear()
    from app import db as db_mod

    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()


def test_flag_snapshot_defaults() -> None:
    flags = flag_snapshot(get_settings())
    assert flags["FEATURE_MANUAL_ENTRY"] is True
    assert flags["FEATURE_RECEIPT_OCR"] is False
    assert flags["PRIVACY_LOCAL_ONLY"] is True


def test_privacy_toggle_override() -> None:
    from app.services import settings_store

    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        assert settings_store.privacy_local_only(db, settings) is True
        settings_store.set_privacy_local_only(db, False)
        assert settings_store.privacy_local_only(db, settings) is False
        assert settings_store.google_vision_allowed(db, settings) is False  # flag/key off
        settings_store.set_privacy_local_only(db, True)
        assert settings_store.privacy_local_only(db, settings) is True


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
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 3),
            amount=Decimal("8.00"),
            currency="EUR",
            merchant="EDEKA",
            category="groceries",
            note="",
        )
        result = expense_service.query_spend(db, settings=settings, q="crisps")
        assert result["count"] == 1
        assert result["total"] == 3.5

        nl = expense_service.query_spend(
            db, settings=settings, q="How much did I spend at REWE this year?"
        )
        assert nl["count"] == 2
        assert nl["total"] == 15.5
        assert nl["filter"]["filter_type"] == "merchant"

        visits = expense_service.query_spend(
            db, settings=settings, q="How many times did I go to edeka?"
        )
        assert visits["count"] == 1
        assert visits["intent"] == "visits"

        shops = expense_service.query_spend(
            db, settings=settings, q="How many times did I go to the shops?"
        )
        assert shops["count"] == 3
        assert shops["filter"]["filter_type"] == "category"

        ans = expense_service.try_deterministic_answer(visits)
        assert ans is not None
        assert "edeka" in ans.lower()


def test_top_5_most_expensive_items_this_month() -> None:
    """Exact user phrase must return ranked line items for this month."""
    os.environ["FEATURE_LINE_ITEMS"] = "true"
    get_settings.cache_clear()
    settings = get_settings()
    SessionLocal = get_session_factory()
    phrase = "top 5 most expensive items this month"
    today = date(2026, 7, 27)
    with SessionLocal() as db:
        cheap = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 10),
            amount=Decimal("20.00"),
            currency="EUR",
            merchant="REWE",
            category="groceries",
        )
        expense_service.replace_line_items(
            db,
            expense_id=cheap.id,
            items=[
                {"description": "Milch", "amount": "1.29"},
                {"description": "Brot", "amount": "2.49"},
            ],
            currency="EUR",
        )
        mid = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 12),
            amount=Decimal("80.00"),
            currency="EUR",
            merchant="MediaMarkt",
            category="household",
        )
        expense_service.replace_line_items(
            db,
            expense_id=mid.id,
            items=[
                {"description": "Kabel", "amount": "19.99"},
                {"description": "Monitor", "amount": "59.00"},
            ],
            currency="EUR",
        )
        # Outside this month — must not appear
        old = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 6, 5),
            amount=Decimal("500.00"),
            currency="EUR",
            merchant="IKEA",
            category="household",
        )
        expense_service.replace_line_items(
            db,
            expense_id=old.id,
            items=[{"description": "Sofa", "amount": "499.00"}],
            currency="EUR",
        )

        # Freeze period via monkeypatch of period_bounds by passing explicit... 
        # query_spend uses period_bounds_for_query with live today — stub by calling
        # with explicit start/end AND parse intent from phrase.
        parsed = expense_service.parse_ask_query(phrase)
        assert parsed["intent"] == "top_expensive"
        assert parsed["wants_items"] is True
        assert parsed["top_n"] == 5

        start, end = expense_service.period_bounds_for_query(phrase, today=today)
        assert start == date(2026, 7, 1)
        assert end == today

        agg = expense_service.query_spend(
            db, settings=settings, q=phrase, start=start, end=end
        )
        assert agg["intent"] == "top_expensive"
        top = agg["top_expensive"]
        assert len(top) >= 3
        assert top[0]["description"] == "Monitor"
        assert Decimal(str(top[0]["amount"])) == Decimal("59.00")
        assert all(r["description"] != "Sofa" for r in top)

        ans = expense_service.try_deterministic_answer(agg)
        assert ans is not None
        assert "Monitor" in ans
        assert "59.00" in ans
        assert "Sofa" not in ans


def test_format_money() -> None:
    assert expense_service.format_money(Decimal("200.0000")) == "200.00"
    assert expense_service.format_money("3.5") == "3.50"


def test_delete_expense() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        row = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 3),
            amount=Decimal("9.99"),
            currency="EUR",
            merchant="Test",
        )
        assert expense_service.delete_expense(db, expense_id=row.id) is True
        assert expense_service.delete_expense(db, expense_id=row.id) is False
        assert expense_service.list_expenses(db) == []
