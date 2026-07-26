"""Expense domain services — shared by HTTP and MCP."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Expense

logger = logging.getLogger("xtav2.expenses")


def add_expense(
    db: Session,
    *,
    settings: Settings,
    spent_on: date,
    amount: Decimal,
    currency: str,
    merchant: str = "",
    category: str = "",
    note: str = "",
    source: str = "manual",
) -> Expense:
    """Persist an expense; copy amount to base when multi-currency is off or same FX."""
    currency_norm = currency.strip().upper()
    base = settings.base_currency.upper()
    amount_base: Decimal | None = None
    base_currency: str | None = None
    if settings.feature_multi_currency:
        # V1: 1:1 when currencies match; FX rates land in a later milestone.
        if currency_norm == base:
            amount_base = amount
            base_currency = base
        else:
            amount_base = None
            base_currency = base
            logger.info(
                "Stored foreign currency without FX conversion",
                extra={"currency": currency_norm, "base": base},
            )
    else:
        amount_base = amount
        base_currency = currency_norm

    row = Expense(
        spent_on=spent_on,
        amount=amount,
        currency=currency_norm,
        amount_base=amount_base,
        base_currency=base_currency,
        merchant=merchant.strip(),
        category=category.strip(),
        note=note.strip(),
        source=source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_expenses(
    db: Session,
    *,
    limit: int = 50,
    category: str | None = None,
    merchant: str | None = None,
    q: str | None = None,
) -> list[Expense]:
    """Return recent expenses with optional filters."""
    stmt: Select[tuple[Expense]] = select(Expense).order_by(Expense.spent_on.desc(), Expense.id.desc())
    if category:
        stmt = stmt.where(Expense.category.ilike(category.strip()))
    if merchant:
        stmt = stmt.where(Expense.merchant.ilike(f"%{merchant.strip()}%"))
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Expense.merchant.ilike(needle),
                Expense.category.ilike(needle),
                Expense.note.ilike(needle),
            )
        )
    stmt = stmt.limit(max(1, min(limit, 200)))
    return list(db.scalars(stmt).all())


def query_spend(
    db: Session,
    *,
    settings: Settings,
    start: date | None = None,
    end: date | None = None,
    q: str | None = None,
) -> dict[str, object]:
    """Sum spend for a window / text filter — MCP and Q&A use this."""
    amount_col = Expense.amount_base if settings.feature_multi_currency else Expense.amount
    currency_label = (
        settings.base_currency.upper() if settings.feature_multi_currency else "mixed"
    )
    stmt = select(func.coalesce(func.sum(amount_col), 0), func.count(Expense.id))
    if start:
        stmt = stmt.where(Expense.spent_on >= start)
    if end:
        stmt = stmt.where(Expense.spent_on <= end)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Expense.merchant.ilike(needle),
                Expense.category.ilike(needle),
                Expense.note.ilike(needle),
            )
        )
    total, count = db.execute(stmt).one()
    return {
        "total": float(total or 0),
        "currency": currency_label,
        "count": int(count or 0),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "q": q,
    }
