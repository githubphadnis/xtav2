"""Bank ↔ receipt reconcile: match and enrich without double-counting."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Expense
from app.services.duplicates import normalize_merchant

logger = logging.getLogger("xtav2.reconcile")

_MONEY_QUANT = Decimal("0.01")
_DATE_WINDOW_DAYS = 1


def _money(amount: Decimal | float | str) -> Decimal:
    return Decimal(str(amount)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


def merchants_similar(a: str, b: str) -> bool:
    """True when merchants overlap or either side is empty (weak match)."""
    na = normalize_merchant(a)
    nb = normalize_merchant(b)
    if not na or not nb:
        return True
    if na in nb or nb in na:
        return True
    ta, tb = set(na.split()), set(nb.split())
    return bool(ta & tb)


def find_reconcile_candidates(
    db: Session,
    *,
    spent_on: date,
    amount: Decimal,
    merchant: str,
    currency: str | None = None,
    exclude_id: int | None = None,
    prefer_sources: tuple[str, ...] | None = None,
) -> list[Expense]:
    """Find posted/pending expenses that may be the same real-world spend."""
    amt = _money(amount)
    low = spent_on - timedelta(days=_DATE_WINDOW_DAYS)
    high = spent_on + timedelta(days=_DATE_WINDOW_DAYS)
    stmt = (
        select(Expense)
        .where(Expense.status.in_(("posted", "pending")))
        .where(Expense.spent_on >= low)
        .where(Expense.spent_on <= high)
        .where(func.abs(Expense.amount - amt) < Decimal("0.005"))
        .order_by(Expense.id.asc())
    )
    if currency:
        stmt = stmt.where(Expense.currency == currency.strip().upper())
    if exclude_id is not None:
        stmt = stmt.where(Expense.id != exclude_id)

    rows = list(db.scalars(stmt).all())
    matched = [r for r in rows if merchants_similar(merchant, r.merchant or "")]
    if prefer_sources:
        preferred = [
            r
            for r in matched
            if r.source in prefer_sources or r.source.startswith("bank")
        ]
        if preferred:
            return preferred
    return matched


def mark_reconciled_source(current: str) -> str:
    """Promote source label after bank↔receipt link."""
    parts = {p for p in (current or "manual").split("+") if p}
    parts.add("bank")
    parts.add("receipt")
    # Stable order for UI
    order = ("bank", "receipt", "manual")
    ordered = [p for p in order if p in parts]
    ordered.extend(sorted(parts - set(order)))
    return "+".join(ordered)


def enrich_bank_with_receipt(
    db: Session,
    *,
    settings: Settings,
    bank: Expense,
    receipt: Expense,
    line_items: list[dict[str, object]] | None = None,
) -> Expense:
    """Attach receipt image + line items onto a bank expense; drop the receipt row.

    Keeps bank amount/date as the posted total (money that left the account).
    """
    from app.services import expenses as expense_service

    if receipt.receipt_path and not bank.receipt_path:
        bank.receipt_path = receipt.receipt_path
    if (not bank.merchant or not bank.merchant.strip()) and receipt.merchant:
        bank.merchant = receipt.merchant.strip()[:255]
    if (not bank.category or not bank.category.strip()) and receipt.category:
        bank.category = receipt.category.strip()[:128]
    if receipt.note and (not bank.note or bank.note.startswith("Bank import")):
        bank.note = receipt.note.strip()

    bank.source = mark_reconciled_source(bank.source)
    if not bank.bank_ref and receipt.bank_ref:
        bank.bank_ref = receipt.bank_ref

    db.commit()
    db.refresh(bank)

    items = line_items
    if items is None and settings.feature_line_items:
        existing = expense_service.list_line_items(db, expense_id=receipt.id)
        items = [
            {
                "description": i.description,
                "quantity": i.quantity,
                "amount": i.amount,
            }
            for i in existing
        ]
    if settings.feature_line_items and items:
        bank_items = expense_service.list_line_items(db, expense_id=bank.id)
        if not bank_items:
            expense_service.replace_line_items(
                db,
                expense_id=bank.id,
                items=items,
                currency=bank.currency,
            )

    # Remove the receipt-only row so Ask counts once.
    expense_service.delete_expense(db, expense_id=receipt.id)
    logger.info(
        "Enriched bank expense #%s from receipt #%s",
        bank.id,
        receipt.id,
        extra={"bank_id": bank.id, "receipt_id": receipt.id},
    )
    db.refresh(bank)
    return bank


def attach_bank_ref_to_expense(
    db: Session,
    *,
    expense: Expense,
    bank_ref: str,
    bank_note: str = "",
) -> Expense:
    """Link a bank CSV row onto an existing receipt/manual expense (no second total)."""
    expense.bank_ref = bank_ref[:128]
    # Receipt/manual already posted — adding bank_ref means reconciled.
    base = expense.source or "manual"
    if "receipt" not in base and expense.receipt_path:
        base = f"{base}+receipt" if base != "receipt" else "receipt"
    expense.source = mark_reconciled_source(base)
    if bank_note and not (expense.note or "").strip():
        expense.note = bank_note[:500]
    db.commit()
    db.refresh(expense)
    return expense


def find_expense_by_bank_ref(db: Session, *, bank_ref: str) -> Expense | None:
    return db.scalars(select(Expense).where(Expense.bank_ref == bank_ref).limit(1)).first()


def expenses_needing_receipt_enrichment(db: Session, *, limit: int = 50) -> list[Expense]:
    """Bank-only posted rows (no receipt image yet)."""
    stmt = (
        select(Expense)
        .where(Expense.status == "posted")
        .where(Expense.bank_ref.is_not(None))
        .where(or_(Expense.receipt_path.is_(None), Expense.receipt_path == ""))
        .order_by(Expense.spent_on.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
