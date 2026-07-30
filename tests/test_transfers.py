"""Non-spend family/savings transfer classification and Ask exclusion."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_MULTI_CURRENCY"] = "true"
os.environ["FEATURE_BANK_IMPORT"] = "true"
os.environ["FEATURE_TRENDS_UI"] = "true"
os.environ["BASE_CURRENCY"] = "EUR"

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.services import expenses as expense_service
from app.services.bank_import import import_bank_csv
from app.services.insights import period_total
from app.services.transfers import (
    classify_transfer_category,
    reclassify_non_spend_transfers,
)

get_settings.cache_clear()


def setup_function() -> None:
    get_settings.cache_clear()
    from app import db as db_mod

    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()


def test_classify_screenshot_phrases() -> None:
    assert classify_transfer_category("To Rashmi Phadnis") == "family"
    assert (
        classify_transfer_category("International Transfer to Rashmi NRE Phadnis")
        == "family"
    )
    assert (
        classify_transfer_category("To pocket EUR Loose Change from EUR") == "savings"
    )
    assert classify_transfer_category("Google Workspace") is None
    assert classify_transfer_category("Polarr") is None


def test_bank_import_tags_family_and_savings() -> None:
    settings = get_settings()
    raw = (
        "Buchungstag;Betrag;Verwendungszweck;Währung\n"
        "16.07.2026;-4540,33;To Rashmi Phadnis;EUR\n"
        "02.07.2026;-0,98;To pocket EUR Loose Change from EUR;EUR\n"
        "01.07.2026;-32,40;Google Workspace;EUR\n"
    ).encode()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        result = import_bank_csv(db, settings=settings, data=raw, filename="n26.csv")
        assert result.created == 3
        rows = {e.merchant: e for e in expense_service.list_expenses(db, limit=20)}
        assert rows["To Rashmi Phadnis"].category == "family"
        assert rows["To pocket EUR Loose Change from EUR"].category == "savings"
        assert rows["Google Workspace"].category == ""


def test_query_spend_and_insights_exclude_non_spend() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 16),
            amount=Decimal("4540.33"),
            currency="EUR",
            merchant="To Rashmi Phadnis",
            category="family",
            source="bank",
        )
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 2),
            amount=Decimal("0.98"),
            currency="EUR",
            merchant="To pocket EUR Loose Change from EUR",
            category="savings",
            source="bank",
        )
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 1),
            amount=Decimal("32.40"),
            currency="EUR",
            merchant="Google Workspace",
            category="software",
            source="bank",
        )
        spend = expense_service.query_spend(
            db,
            settings=settings,
            start=date(2026, 7, 1),
            end=date(2026, 7, 31),
        )
        assert float(spend["total"]) == 32.40
        assert spend["count"] == 1

        pulse_slice = period_total(
            db,
            settings=settings,
            start=date(2026, 7, 1),
            end=date(2026, 7, 31),
            label="Jul",
        )
        assert pulse_slice.total == Decimal("32.40")
        assert pulse_slice.count == 1


def test_reclassify_existing_rows() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 1),
            amount=Decimal("2317.29"),
            currency="EUR",
            merchant="To Rashmi Phadnis",
            category="",
            source="bank",
        )
        n = reclassify_non_spend_transfers(db)
        assert n == 1
        row = expense_service.list_expenses(db, limit=5)[0]
        assert row.category == "family"
