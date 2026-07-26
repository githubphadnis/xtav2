"""Expense domain services — shared by HTTP and MCP."""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Expense, ExpenseLineItem

logger = logging.getLogger("xtav2.expenses")

_MONEY_QUANT = Decimal("0.01")
_STOPWORDS = frozenset(
    {
        "how",
        "much",
        "did",
        "i",
        "spend",
        "spent",
        "at",
        "on",
        "in",
        "the",
        "a",
        "an",
        "this",
        "that",
        "year",
        "month",
        "week",
        "quarter",
        "last",
        "what",
        "when",
        "where",
        "was",
        "were",
        "for",
        "from",
        "with",
        "about",
        "total",
        "all",
        "my",
        "me",
        "to",
        "of",
        "and",
        "or",
        "tis",
    }
)


def format_money(amount: Decimal | float | str) -> str:
    """Format amounts for UI as two decimal places."""
    value = Decimal(str(amount)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    return f"{value:.2f}"


def search_tokens(q: str) -> list[str]:
    """Extract meaningful tokens from a natural-language spend question."""
    tokens = re.findall(r"[A-Za-z0-9]{2,}", q or "")
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        key = token.lower()
        if key in _STOPWORDS or key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out


def _text_match_clause(q: str) -> ColumnElement[bool] | None:
    """Build OR clause over merchant/category/note/line descriptions."""
    raw = (q or "").strip()
    if not raw:
        return None
    tokens = search_tokens(raw)
    needles = [f"%{t}%" for t in tokens] if tokens else [f"%{raw}%"]
    clauses = []
    for needle in needles:
        clauses.append(
            or_(
                Expense.merchant.ilike(needle),
                Expense.category.ilike(needle),
                Expense.note.ilike(needle),
                Expense.id.in_(
                    select(ExpenseLineItem.expense_id).where(
                        ExpenseLineItem.description.ilike(needle)
                    )
                ),
            )
        )
    return or_(*clauses) if clauses else None


def replace_line_items(
    db: Session,
    *,
    expense_id: int,
    items: list[dict[str, object]],
    currency: str,
) -> list[ExpenseLineItem]:
    """Replace all line items for an expense (empty list clears)."""
    existing = list(
        db.scalars(
            select(ExpenseLineItem).where(ExpenseLineItem.expense_id == expense_id)
        ).all()
    )
    for row in existing:
        db.delete(row)
    db.flush()

    currency_norm = currency.strip().upper()[:3] or "EUR"
    created: list[ExpenseLineItem] = []
    for idx, raw in enumerate(items):
        desc = str(raw.get("description") or "").strip()
        if not desc:
            continue
        try:
            amount = Decimal(str(raw.get("amount") or "0").replace(",", ".")).quantize(
                _MONEY_QUANT, rounding=ROUND_HALF_UP
            )
        except (InvalidOperation, ValueError):
            amount = Decimal("0.00")
        qty: Decimal | None = None
        if raw.get("quantity") is not None and str(raw.get("quantity")).strip() != "":
            try:
                qty = Decimal(str(raw["quantity"]).replace(",", "."))
            except (InvalidOperation, ValueError):
                qty = None
        row = ExpenseLineItem(
            expense_id=expense_id,
            description=desc[:512],
            quantity=qty,
            amount=amount,
            currency=currency_norm,
            position=idx,
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return created


def list_line_items(db: Session, *, expense_id: int) -> list[ExpenseLineItem]:
    return list(
        db.scalars(
            select(ExpenseLineItem)
            .where(ExpenseLineItem.expense_id == expense_id)
            .order_by(ExpenseLineItem.position, ExpenseLineItem.id)
        ).all()
    )


def query_line_matches(
    db: Session,
    *,
    q: str | None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, object]]:
    """Return posted line items matching q tokens (for Ask grounding)."""
    if not (q or "").strip():
        return []
    tokens = search_tokens(q or "")
    if not tokens:
        return []
    stmt = (
        select(ExpenseLineItem, Expense)
        .join(Expense, Expense.id == ExpenseLineItem.expense_id)
        .where(Expense.status == "posted")
    )
    if start:
        stmt = stmt.where(Expense.spent_on >= start)
    if end:
        stmt = stmt.where(Expense.spent_on <= end)
    desc_clauses = [ExpenseLineItem.description.ilike(f"%{t}%") for t in tokens]
    stmt = stmt.where(or_(*desc_clauses)).order_by(Expense.spent_on.desc()).limit(50)
    rows = db.execute(stmt).all()
    out: list[dict[str, object]] = []
    for item, exp in rows:
        out.append(
            {
                "expense_id": exp.id,
                "spent_on": exp.spent_on.isoformat(),
                "merchant": exp.merchant,
                "description": item.description,
                "amount": float(
                    Decimal(str(item.amount)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
                ),
                "currency": item.currency,
            }
        )
    return out


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
    status: str = "posted",
    receipt_path: str | None = None,
) -> Expense:
    """Persist an expense; copy amount to base when multi-currency is off or same FX."""
    amount = amount.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
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
        status=status,
        receipt_path=receipt_path,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_expense(
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
    status: str | None = None,
) -> Expense | None:
    """Update fields on an expense; optionally change status (e.g. pending → posted)."""
    row = db.get(Expense, expense_id)
    if row is None:
        return None
    amount = amount.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    currency_norm = currency.strip().upper()
    row.spent_on = spent_on
    row.amount = amount
    row.currency = currency_norm
    row.merchant = merchant.strip()
    row.category = category.strip()
    row.note = note.strip()
    if status is not None:
        row.status = status
    if settings.feature_multi_currency and currency_norm == settings.base_currency.upper():
        row.amount_base = amount
        row.base_currency = currency_norm
    db.commit()
    db.refresh(row)
    return row


def delete_expense(db: Session, *, expense_id: int) -> bool:
    """Delete an expense by id. Returns True if a row was removed."""
    row = db.get(Expense, expense_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def list_expenses(
    db: Session,
    *,
    limit: int = 50,
    category: str | None = None,
    merchant: str | None = None,
    q: str | None = None,
    status: str | None = "posted",
) -> list[Expense]:
    """Return recent expenses with optional filters (default: posted only)."""
    stmt: Select[tuple[Expense]] = select(Expense).order_by(
        Expense.spent_on.desc(), Expense.id.desc()
    )
    if status is not None:
        stmt = stmt.where(Expense.status == status)
    if category:
        stmt = stmt.where(Expense.category.ilike(category.strip()))
    if merchant:
        stmt = stmt.where(Expense.merchant.ilike(f"%{merchant.strip()}%"))
    text_clause = _text_match_clause(q) if q else None
    if text_clause is not None:
        stmt = stmt.where(text_clause)
    stmt = stmt.limit(max(1, min(limit, 200)))
    return list(db.scalars(stmt).all())


def list_pending(db: Session, *, limit: int = 50) -> list[Expense]:
    """Return pending receipt drafts newest first."""
    return list_expenses(db, limit=limit, status="pending")


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
    stmt = select(func.coalesce(func.sum(amount_col), 0), func.count(Expense.id)).where(
        Expense.status == "posted"
    )
    if start:
        stmt = stmt.where(Expense.spent_on >= start)
    if end:
        stmt = stmt.where(Expense.spent_on <= end)
    text_clause = _text_match_clause(q) if q else None
    if text_clause is not None:
        stmt = stmt.where(text_clause)
    total, count = db.execute(stmt).one()
    line_matches: list[dict[str, object]] = []
    line_total = 0.0
    if q and settings.feature_line_items:
        line_matches = query_line_matches(db, q=q, start=start, end=end)
        line_total = float(
            sum(
                (
                    Decimal(str(m["amount"])).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
                    for m in line_matches
                ),
                Decimal("0.00"),
            )
        )
    return {
        "total": float(
            Decimal(str(total or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        ),
        "currency": currency_label,
        "count": int(count or 0),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "q": q,
        "tokens": search_tokens(q) if q else [],
        "line_matches": line_matches,
        "line_total": line_total,
        "line_match_count": len(line_matches),
    }
