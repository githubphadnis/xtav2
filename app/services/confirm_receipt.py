"""Confirm a pending receipt, enriching a matched bank row when possible."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Expense
from app.services import expenses as expense_service
from app.services.reconcile import enrich_bank_with_receipt, find_reconcile_candidates


def confirm_receipt_expense(
    db: Session,
    *,
    settings: Settings,
    expense_id: int,
    spent_on: date,
    amount: Decimal,
    currency: str,
    merchant: str = "",
    category: str = "",
    note: str = "",
    line_items: list[dict[str, object]] | None = None,
) -> tuple[Expense | None, str]:
    """Post a pending receipt, or merge into a matching bank expense.

    Returns (resulting expense, flash message).
    """
    row = db.get(Expense, expense_id)
    if row is None:
        return None, "Expense not found"

    items = line_items or []

    if settings.feature_bank_import:
        banks = find_reconcile_candidates(
            db,
            spent_on=spent_on,
            amount=amount,
            merchant=merchant,
            currency=currency,
            exclude_id=expense_id,
            prefer_sources=("bank",),
        )
        bank = next(
            (
                b
                for b in banks
                if b.source.startswith("bank")
                or (b.bank_ref and not b.receipt_path)
            ),
            None,
        )
        if bank is None:
            bank = next((b for b in banks if b.bank_ref and not b.receipt_path), None)

        if bank is not None:
            # Apply confirmed fields onto the receipt row first (merchant/path).
            row.spent_on = spent_on
            row.amount = amount
            row.currency = currency.strip().upper()
            row.merchant = merchant.strip()
            row.category = category.strip()
            row.note = note.strip()
            db.commit()
            enriched = enrich_bank_with_receipt(
                db,
                settings=settings,
                bank=bank,
                receipt=row,
                line_items=items if settings.feature_line_items else None,
            )
            return enriched, (
                f"Linked receipt to bank expense #{enriched.id} "
                f"(line items attached; counted once)."
            )

    updated = expense_service.update_expense(
        db,
        settings=settings,
        expense_id=expense_id,
        spent_on=spent_on,
        amount=amount,
        currency=currency,
        merchant=merchant,
        category=category,
        note=note,
        status="posted",
    )
    if updated is None:
        return None, "Expense not found"

    if settings.feature_line_items and items is not None:
        expense_service.replace_line_items(
            db, expense_id=expense_id, items=items, currency=currency
        )
    return updated, "Receipt posted."
