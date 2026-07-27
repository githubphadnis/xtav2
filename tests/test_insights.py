"""Insights Phase 1 aggregate tests."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_MULTI_CURRENCY"] = "true"
os.environ["FEATURE_TRENDS_UI"] = "true"
os.environ["BASE_CURRENCY"] = "EUR"

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.services import expenses as expense_service
from app.services.insights import (
    build_pulse,
    month_windows,
    period_total,
    rolling_month_windows,
)

get_settings.cache_clear()


def setup_function() -> None:
    get_settings.cache_clear()
    from app import db as db_mod

    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()


def test_month_windows_like_for_like() -> None:
    this_start, this_end, last_start, last_end = month_windows(date(2026, 7, 27))
    assert this_start == date(2026, 7, 1)
    assert this_end == date(2026, 7, 27)
    assert last_start == date(2026, 6, 1)
    assert last_end == date(2026, 6, 27)


def test_rolling_three_months_full_priors_mtd_current() -> None:
    windows = rolling_month_windows(date(2026, 7, 27), months=3)
    assert len(windows) == 3
    assert windows[0] == (date(2026, 5, 1), date(2026, 5, 31), "May")
    assert windows[1] == (date(2026, 6, 1), date(2026, 6, 30), "Jun")
    assert windows[2] == (date(2026, 7, 1), date(2026, 7, 27), "Jul")


def test_bar_height_rem_scales_and_avoids_zero_collapse() -> None:
    from app.services.insights import bar_height_rem

    assert bar_height_rem(Decimal(0), Decimal(100)) == 0.25
    assert bar_height_rem(Decimal(100), Decimal(100), max_rem=8.0) == 8.0
    assert bar_height_rem(Decimal(50), Decimal(100), max_rem=8.0) == 4.0


def test_pulse_matches_query_spend() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    today = date(2026, 7, 27)
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 10),
            amount=Decimal("40.00"),
            currency="EUR",
            merchant="REWE",
            category="groceries",
        )
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 12),
            amount=Decimal("20.00"),
            currency="EUR",
            merchant="EDEKA",
            category="groceries",
        )
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 6, 5),
            amount=Decimal("30.00"),
            currency="EUR",
            merchant="REWE",
            category="groceries",
        )
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 6, 28),
            amount=Decimal("100.00"),
            currency="EUR",
            merchant="IKEA",
            category="household",
        )

        pulse = build_pulse(db, settings=settings, today=today)
        assert pulse.this_month.total == Decimal("60.00")
        assert pulse.last_month.total == Decimal("30.00")  # Jun 28 excluded (after day 27)
        assert pulse.delta == Decimal("30.00")

        qs = expense_service.query_spend(
            db,
            settings=settings,
            start=pulse.this_month.start,
            end=pulse.this_month.end,
        )
        assert Decimal(str(qs["total"])) == pulse.this_month.total

        assert pulse.categories[0].key == "groceries"
        assert pulse.categories[0].total == Decimal("60.00")
        assert any(m.key == "REWE" for m in pulse.merchants)
        assert len(pulse.trend_months) == 3
        assert pulse.trend_months[-1].total == Decimal("60.00")
        assert pulse.trend_months[1].total == Decimal("130.00")  # full June


def test_period_total_excludes_active_duplicates() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        a = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 1),
            amount=Decimal("10.00"),
            currency="EUR",
            merchant="Same",
            category="other",
        )
        b = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 1),
            amount=Decimal("10.00"),
            currency="EUR",
            merchant="Same",
            category="other",
        )
        # One should be flagged duplicate by fingerprint
        assert a.duplicate_of_id or b.duplicate_of_id
        total = period_total(
            db,
            settings=settings,
            start=date(2026, 7, 1),
            end=date(2026, 7, 31),
            label="Jul",
        )
        assert total.total == Decimal("10.00")
        assert total.count == 1
