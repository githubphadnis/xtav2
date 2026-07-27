"""Bank CSV parse + reconcile tests."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_MULTI_CURRENCY"] = "true"
os.environ["FEATURE_BANK_IMPORT"] = "true"
os.environ["FEATURE_LINE_ITEMS"] = "true"
os.environ["FEATURE_RECEIPT_OCR"] = "true"
os.environ["BASE_CURRENCY"] = "EUR"

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.services import expenses as expense_service
from app.services.bank_csv import parse_bank_csv
from app.services.bank_import import import_bank_csv
from app.services.confirm_receipt import confirm_receipt_expense
from app.services.reconcile import find_reconcile_candidates

get_settings.cache_clear()


def setup_function() -> None:
    get_settings.cache_clear()
    from app import db as db_mod

    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()


def test_parse_german_signed_csv() -> None:
    raw = (
        "Buchungstag;Betrag;Verwendungszweck;Währung\n"
        "25.07.2026;-19,32;REWE SAGT DANKE;EUR\n"
        "25.07.2026;1500,00;GEHALT;EUR\n"
    ).encode()
    rows = parse_bank_csv(raw, default_currency="EUR", filename="n26.csv")
    assert len(rows) == 1
    assert rows[0].amount == Decimal("19.32")
    assert rows[0].merchant.startswith("REWE")
    assert rows[0].spent_on == date(2026, 7, 25)


def test_bank_then_receipt_enriches_once() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        bank = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 25),
            amount=Decimal("19.32"),
            currency="EUR",
            merchant="REWE SAGT DANKE",
            source="bank",
            bank_ref="test:1",
        )
        receipt = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 25),
            amount=Decimal("19.32"),
            currency="EUR",
            merchant="REWE",
            category="groceries",
            source="receipt",
            status="pending",
            receipt_path="r1.jpg",
        )
        result, flash = confirm_receipt_expense(
            db,
            settings=settings,
            expense_id=receipt.id,
            spent_on=date(2026, 7, 25),
            amount=Decimal("19.32"),
            currency="EUR",
            merchant="REWE",
            category="groceries",
            note="",
            line_items=[
                {"description": "Schokolade", "amount": "1.99"},
                {"description": "Milch", "amount": "1.29"},
            ],
        )
        assert result is not None
        assert result.id == bank.id
        assert "bank" in flash.lower() or "linked" in flash.lower()
        assert result.receipt_path == "r1.jpg"
        assert "receipt" in result.source
        items = expense_service.list_line_items(db, expense_id=bank.id)
        assert len(items) == 2
        from app.models import Expense

        assert db.get(Expense, receipt.id) is None
        posted = expense_service.list_expenses(db, limit=20)
        assert len(posted) == 1
        agg = expense_service.query_spend(
            db, settings=settings, q="How much at REWE?"
        )
        assert Decimal(str(agg["total"])) == Decimal("19.32")


def test_receipt_then_bank_links_without_second_row() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 25),
            amount=Decimal("19.32"),
            currency="EUR",
            merchant="REWE",
            source="receipt",
            status="posted",
            receipt_path="r2.jpg",
        )
        csv_data = (
            b"date,amount,merchant,currency\n"
            b"2026-07-25,-19.32,REWE Markt,EUR\n"
        )
        result = import_bank_csv(
            db, settings=settings, data=csv_data, filename="stmt.csv"
        )
        assert result.created == 0
        assert result.linked == 1
        rows = expense_service.list_expenses(db, limit=20)
        assert len(rows) == 1
        assert rows[0].bank_ref
        assert "bank" in rows[0].source


def test_find_candidates_date_window() -> None:
    settings = get_settings()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        expense_service.add_expense(
            db,
            settings=settings,
            spent_on=date(2026, 7, 25),
            amount=Decimal("10.00"),
            currency="EUR",
            merchant="Edeka",
            source="bank",
            bank_ref="x",
        )
        found = find_reconcile_candidates(
            db,
            spent_on=date(2026, 7, 26),
            amount=Decimal("10.00"),
            merchant="EDEKA Berlin",
            currency="EUR",
        )
        assert len(found) == 1
