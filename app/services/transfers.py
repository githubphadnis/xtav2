"""Family / pocket transfers — keep on ledger, exclude from spend totals."""

from __future__ import annotations

from sqlalchemy import func, not_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import Expense

NON_SPEND_CATEGORIES = frozenset({"family", "savings"})

# Substrings matched against merchant + note (case-insensitive).
_FAMILY_MARKERS = (
    "rashmi",
    "nre",
    "family support",
)
_SAVINGS_MARKERS = (
    "loose change",
    "to pocket",
    "pocket eur",
)


def is_non_spend_category(category: str | None) -> bool:
    """True when category is family/savings (not counted as spend)."""
    return (category or "").strip().lower() in NON_SPEND_CATEGORIES


def classify_transfer_category(merchant: str = "", note: str = "") -> str | None:
    """Return ``family`` / ``savings`` when text looks like a non-spend transfer."""
    text = f"{merchant} {note}".casefold()
    if any(marker in text for marker in _SAVINGS_MARKERS):
        return "savings"
    if any(marker in text for marker in _FAMILY_MARKERS):
        return "family"
    return None


def exclude_non_spend() -> ColumnElement[bool]:
    """SQL filter: drop family/savings categories from spend aggregates."""
    return not_(
        func.lower(func.coalesce(Expense.category, "")).in_(sorted(NON_SPEND_CATEGORIES))
    )


def reclassify_non_spend_transfers(db: Session) -> int:
    """Set category on posted rows whose merchant/note match transfer patterns.

    Returns number of rows updated.
    """
    rows = list(db.scalars(select(Expense).where(Expense.status == "posted")).all())
    updated = 0
    for row in rows:
        wanted = classify_transfer_category(row.merchant or "", row.note or "")
        if wanted is None:
            continue
        current = (row.category or "").strip().lower()
        if current == wanted:
            continue
        row.category = wanted
        updated += 1
    if updated:
        db.commit()
    return updated
