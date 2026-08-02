"""Mass rename find/replace tests."""

from __future__ import annotations

import logging
import os
from datetime import date
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_MULTI_CURRENCY"] = "true"
os.environ["FEATURE_LINE_ITEMS"] = "true"
os.environ["FEATURE_MASS_RENAME"] = "true"
os.environ["FEATURE_RECEIPT_OCR"] = "false"
os.environ["FEATURE_OCR_GOOGLE_VISION"] = "false"
os.environ["PRIVACY_LOCAL_ONLY"] = "true"
os.environ["GOOGLE_VISION_API_KEY"] = ""
os.environ["BASE_CURRENCY"] = "EUR"

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.features import flag_snapshot
from app.services import expenses as expense_service
from app.services import mass_rename

get_settings.cache_clear()


def setup_function() -> None:
    os.environ["FEATURE_LINE_ITEMS"] = "true"
    os.environ["FEATURE_MASS_RENAME"] = "true"
    get_settings.cache_clear()
    from app import db as db_mod

    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()


def test_flag_snapshot_includes_mass_rename() -> None:
    flags = flag_snapshot(get_settings())
    assert flags["FEATURE_MASS_RENAME"] is True


def test_lucky_strike_merchant_rename() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 1),
            amount=Decimal("12.50"),
            currency="EUR",
            merchant="Lucky Strike",
            category="other",
            note="",
        )
        preview = mass_rename.preview_rename(db, find="Lucky Strike")
        assert preview.match_count == 1
        assert preview.samples[0].merchant == "Lucky Strike"

        result = mass_rename.apply_rename(
            db,
            find="Lucky Strike",
            replace="Lucky",
            confirm=True,
        )
        assert result.expenses_touched == 1
        assert result.fields_changed == 1

        rows = expense_service.list_expenses(db, merchant="Lucky")
        assert len(rows) == 1
        assert rows[0].merchant == "Lucky"
        assert not expense_service.list_expenses(db, merchant="Lucky Strike")


def test_playboy_note_substring_and_full_replace() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 2),
            amount=Decimal("29.00"),
            currency="EUR",
            merchant="Newsstand",
            note="Subscription to Playboy",
        )
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 3),
            amount=Decimal("9.00"),
            currency="EUR",
            merchant="Kiosk",
            note="Subscription to Playboy",
        )

        # Substring: Playboy → Printing Services
        mass_rename.apply_rename(
            db,
            find="Playboy",
            replace="Printing Services",
            confirm=True,
        )
        rows = expense_service.list_expenses(db, limit=10)
        notes = {r.note for r in rows}
        assert notes == {"Subscription to Printing Services"}

        # Full-field find/replace
        mass_rename.apply_rename(
            db,
            find="Subscription to Printing Services",
            replace="Printing Services",
            confirm=True,
        )
        rows = expense_service.list_expenses(db, limit=10)
        assert all(r.note == "Printing Services" for r in rows)


def test_line_item_description_rename() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        row = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 4),
            amount=Decimal("5.00"),
            currency="EUR",
            merchant="Shop",
            note="",
        )
        expense_service.replace_line_items(
            db,
            expense_id=row.id,
            items=[{"description": "Lucky Strike Pack", "amount": "5.00"}],
            currency="EUR",
        )
        mass_rename.apply_rename(
            db,
            find="Lucky Strike",
            replace="Lucky",
            confirm=True,
            include_line_items=True,
        )
        items = expense_service.list_line_items(db, expense_id=row.id)
        assert items[0].description == "Lucky Pack"


def test_preview_does_not_mutate() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 5),
            amount=Decimal("1.00"),
            currency="EUR",
            merchant="Lucky Strike",
        )
        mass_rename.preview_rename(db, find="Lucky Strike")
        rows = expense_service.list_expenses(db, merchant="Lucky Strike")
        assert len(rows) == 1
        assert rows[0].merchant == "Lucky Strike"


def test_apply_requires_confirm_and_rejects_empty_find() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 6),
            amount=Decimal("1.00"),
            currency="EUR",
            merchant="Lucky Strike",
        )
        try:
            mass_rename.apply_rename(
                db, find="Lucky Strike", replace="Lucky", confirm=False
            )
            raise AssertionError("expected MassRenameError")
        except mass_rename.MassRenameError as exc:
            assert "Confirm" in str(exc)

        try:
            mass_rename.preview_rename(db, find="  ")
            raise AssertionError("expected MassRenameError")
        except mass_rename.MassRenameError as exc:
            assert "required" in str(exc).lower()


def test_case_insensitive_match() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 7),
            amount=Decimal("2.00"),
            currency="EUR",
            merchant="Lucky Strike",
        )
        preview = mass_rename.preview_rename(db, find="lucky strike")
        assert preview.match_count == 1
        mass_rename.apply_rename(
            db, find="lucky strike", replace="Lucky", confirm=True
        )
        rows = expense_service.list_expenses(db, merchant="Lucky")
        assert len(rows) == 1
        assert rows[0].merchant == "Lucky"


def test_logs_do_not_include_find_replace_strings(
    caplog: object,
) -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 8),
            amount=Decimal("3.00"),
            currency="EUR",
            merchant="SecretBrandXYZ",
        )
        with caplog.at_level(logging.INFO, logger="xtav2.mass_rename"):
            mass_rename.apply_rename(
                db,
                find="SecretBrandXYZ",
                replace="NeutralShop",
                confirm=True,
            )
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "SecretBrandXYZ" not in joined
        assert "NeutralShop" not in joined
