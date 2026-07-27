"""FX conversion tests."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_MULTI_CURRENCY"] = "true"
os.environ["BASE_CURRENCY"] = "EUR"

from app.config import Settings, get_settings
from app.db import get_session_factory, init_db
from app.services import expenses as expense_service
from app.services.fx import convert_amount, to_base_amount

get_settings.cache_clear()


def setup_function() -> None:
    get_settings.cache_clear()
    from app import db as db_mod
    from app.services import fx as fx_mod

    fx_mod._fetch_rate_cached.cache_clear()
    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()


def test_convert_amount() -> None:
    assert convert_amount(Decimal("10.00"), rate=Decimal("0.920000")) == Decimal("9.20")


def test_same_currency_no_api() -> None:
    settings = Settings(base_currency="EUR", feature_multi_currency=True)
    base, rate, err = to_base_amount(
        settings,
        amount=Decimal("12.50"),
        currency="EUR",
        spent_on=date(2026, 7, 1),
    )
    assert err is None
    assert base == Decimal("12.50")
    assert rate == Decimal("1")


def test_foreign_with_override() -> None:
    settings = Settings(base_currency="EUR", feature_multi_currency=True)
    base, rate, err = to_base_amount(
        settings,
        amount=Decimal("100.00"),
        currency="USD",
        spent_on=date(2026, 7, 1),
        fx_rate_override=Decimal("0.90"),
    )
    assert err is None
    assert rate == Decimal("0.900000")
    assert base == Decimal("90.00")


def test_add_expense_converts_with_mocked_rate() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with (
        patch("app.services.fx._fetch_rate_cached", return_value="0.85"),
        SessionLocal() as db,
    ):
        row = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 6, 15),
            amount=Decimal("20.00"),
            currency="USD",
            merchant="Airport",
            status="posted",
        )
        assert row.amount == Decimal("20.00")
        assert row.currency == "USD"
        assert row.amount_base == Decimal("17.00")
        assert row.base_currency == "EUR"
        total = expense_service.query_spend(db, settings=settings)
        assert total["total"] == 17.0
        assert total["currency"] == "EUR"
