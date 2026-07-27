"""Duplicate expense detection via fingerprints."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense, ExpenseLineItem

_LEGAL_NOISE = re.compile(
    r"\b(gmbh|co\.?|kg|ag|ltd|llc|inc|ug|ohg|e\.?\s*k\.?|&)\b",
    re.IGNORECASE,
)
_MONEY_QUANT = Decimal("0.01")


def _money(amount: Decimal | float | str) -> str:
    value = Decimal(str(amount)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    return f"{value:.2f}"


def normalize_merchant(merchant: str) -> str:
    text = (merchant or "").lower().strip()
    text = _LEGAL_NOISE.sub(" ", text)
    text = re.sub(r"[^a-z0-9äöüß]+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def items_signature(db: Session, *, expense_id: int) -> str:
    rows = list(
        db.scalars(
            select(ExpenseLineItem)
            .where(ExpenseLineItem.expense_id == expense_id)
            .order_by(ExpenseLineItem.position, ExpenseLineItem.id)
        ).all()
    )
    if not rows:
        return ""
    parts = [
        f"{(r.description or '').strip().lower()}|{_money(r.amount)}" for r in rows
    ]
    parts.sort()
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def compute_fingerprint(
    *,
    spent_on: date,
    amount: Decimal,
    merchant: str,
    items_sig: str = "",
) -> str | None:
    """Stable fingerprint. None when too weak to match safely."""
    amt = _money(amount)
    merch = normalize_merchant(merchant)
    if Decimal(amt) <= 0:
        return None
    # Need merchant or line items — date+amount alone is too collision-prone.
    if not merch and not items_sig:
        return None
    raw = f"{spent_on.isoformat()}|{amt}|{merch}|{items_sig}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_active_duplicate(row: Expense) -> bool:
    """True when flagged as duplicate and not dismissed by the operator."""
    return bool(row.duplicate_of_id) and not bool(row.duplicate_dismissed)


def refresh_duplicate_link(db: Session, *, expense_id: int) -> Expense | None:
    """Recompute fingerprint and link to an older matching expense if found."""
    row = db.get(Expense, expense_id)
    if row is None:
        return None
    if row.status not in {"pending", "posted"}:
        return row

    items_sig = items_signature(db, expense_id=expense_id)
    fp = compute_fingerprint(
        spent_on=row.spent_on,
        amount=row.amount,
        merchant=row.merchant or "",
        items_sig=items_sig,
    )
    row.fingerprint = fp

    if fp is None:
        row.duplicate_of_id = None
        db.commit()
        db.refresh(row)
        return row

    if row.duplicate_dismissed:
        db.commit()
        db.refresh(row)
        return row

    twin = db.scalars(
        select(Expense)
        .where(
            Expense.fingerprint == fp,
            Expense.id != expense_id,
            Expense.status.in_(("pending", "posted")),
            Expense.duplicate_of_id.is_(None),
        )
        .order_by(Expense.id.asc())
        .limit(1)
    ).first()

    if twin is not None and twin.id < expense_id:
        row.duplicate_of_id = twin.id
    elif twin is not None and twin.id > expense_id:
        twin.duplicate_of_id = expense_id
        twin.duplicate_dismissed = False
        row.duplicate_of_id = None
    else:
        row.duplicate_of_id = None

    db.commit()
    db.refresh(row)
    return row


def dismiss_duplicate(db: Session, *, expense_id: int) -> Expense | None:
    """Operator says this is not a duplicate — keep it in Ask totals."""
    row = db.get(Expense, expense_id)
    if row is None:
        return None
    row.duplicate_dismissed = True
    db.commit()
    db.refresh(row)
    return row


def count_active_duplicates(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(Expense.id)).where(
                Expense.duplicate_of_id.is_not(None),
                Expense.duplicate_dismissed.is_(False),
            )
        )
        or 0
    )


def rescan_all_duplicates(db: Session, *, limit: int = 500) -> int:
    """Re-link fingerprints for recent pending/posted rows (post-deploy catch-up)."""
    rows = list(
        db.scalars(
            select(Expense)
            .where(Expense.status.in_(("pending", "posted")))
            .order_by(Expense.id.desc())
            .limit(limit)
        ).all()
    )
    for row in sorted(rows, key=lambda r: r.id):
        refresh_duplicate_link(db, expense_id=row.id)
    return len(rows)
