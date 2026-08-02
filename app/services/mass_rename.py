"""Mass rename — find/replace merchant, note, and line-item text."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Expense, ExpenseLineItem
from app.services.duplicates import refresh_duplicate_link

logger = logging.getLogger("xtav2.mass_rename")

_MAX_APPLY_ROWS = 5000
_SAMPLE_LIMIT = 20
_ACTIVE_STATUSES = ("posted", "pending")


class MassRenameError(ValueError):
    """User-facing validation / guardrail failure."""


@dataclass
class RenameSample:
    id: int
    spent_on: date
    merchant: str
    note: str
    line_hits: list[str] = field(default_factory=list)


@dataclass
class PreviewResult:
    match_count: int
    field_hit_count: int
    samples: list[RenameSample]


@dataclass
class ApplyResult:
    expenses_touched: int
    fields_changed: int


def _validate_terms(find: str, replace: str | None = None) -> str:
    needle = (find or "").strip()
    if not needle:
        raise MassRenameError("Find text is required")
    if replace is not None and needle.casefold() == (replace or "").strip().casefold():
        raise MassRenameError("Find and replace text must differ")
    return needle


def _ci_contains(haystack: str, needle: str) -> bool:
    return bool(haystack) and needle.casefold() in haystack.casefold()


def _ci_replace(text: str, needle: str, replacement: str) -> str:
    if not text or not needle:
        return text
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    return pattern.sub(replacement, text)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _candidate_ids(
    db: Session,
    *,
    needle: str,
    include_line_items: bool,
) -> list[int]:
    """Return expense ids that may contain needle (SQL prefilter)."""
    like = f"%{_escape_like(needle)}%"
    clauses = [
        Expense.merchant.ilike(like, escape="\\"),
        Expense.note.ilike(like, escape="\\"),
    ]
    if include_line_items:
        line_ids = select(ExpenseLineItem.expense_id).where(
            ExpenseLineItem.description.ilike(like, escape="\\")
        )
        clauses.append(Expense.id.in_(line_ids))

    stmt = (
        select(Expense.id)
        .where(Expense.status.in_(_ACTIVE_STATUSES))
        .where(or_(*clauses))
        .order_by(Expense.spent_on.desc(), Expense.id.desc())
    )
    return list(db.scalars(stmt).all())


def _load_expenses(db: Session, ids: list[int]) -> list[Expense]:
    if not ids:
        return []
    rows = list(
        db.scalars(
            select(Expense)
            .where(Expense.id.in_(ids))
            .options(selectinload(Expense.line_items))
        ).all()
    )
    by_id = {r.id: r for r in rows}
    return [by_id[i] for i in ids if i in by_id]


def _field_hits(
    row: Expense,
    *,
    needle: str,
    include_line_items: bool,
) -> tuple[bool, list[str]]:
    """Return (expense_matches, matching line descriptions)."""
    merchant_hit = _ci_contains(row.merchant or "", needle)
    note_hit = _ci_contains(row.note or "", needle)
    line_hits: list[str] = []
    if include_line_items:
        for item in row.line_items or []:
            desc = item.description or ""
            if _ci_contains(desc, needle):
                line_hits.append(desc)
    return merchant_hit or note_hit or bool(line_hits), line_hits


def preview_rename(
    db: Session,
    *,
    find: str,
    include_line_items: bool = True,
) -> PreviewResult:
    """Count and sample matches without mutating rows."""
    needle = _validate_terms(find)
    ids = _candidate_ids(db, needle=needle, include_line_items=include_line_items)
    rows = _load_expenses(db, ids)

    samples: list[RenameSample] = []
    match_count = 0
    field_hit_count = 0
    for row in rows:
        matches, line_hits = _field_hits(
            row, needle=needle, include_line_items=include_line_items
        )
        if not matches:
            continue
        match_count += 1
        if _ci_contains(row.merchant or "", needle):
            field_hit_count += 1
        if _ci_contains(row.note or "", needle):
            field_hit_count += 1
        field_hit_count += len(line_hits)
        if len(samples) < _SAMPLE_LIMIT:
            samples.append(
                RenameSample(
                    id=row.id,
                    spent_on=row.spent_on,
                    merchant=row.merchant or "",
                    note=row.note or "",
                    line_hits=line_hits[:5],
                )
            )

    return PreviewResult(
        match_count=match_count,
        field_hit_count=field_hit_count,
        samples=samples,
    )


def apply_rename(
    db: Session,
    *,
    find: str,
    replace: str,
    confirm: bool,
    include_line_items: bool = True,
) -> ApplyResult:
    """Replace all case-insensitive occurrences of find; refresh fingerprints."""
    if not confirm:
        raise MassRenameError("Confirm is required before applying rename")
    needle = _validate_terms(find, replace)
    replacement = replace if replace is not None else ""

    ids = _candidate_ids(db, needle=needle, include_line_items=include_line_items)
    rows = _load_expenses(db, ids)

    matched: list[Expense] = []
    for row in rows:
        matches, _ = _field_hits(
            row, needle=needle, include_line_items=include_line_items
        )
        if matches:
            matched.append(row)

    if len(matched) > _MAX_APPLY_ROWS:
        raise MassRenameError(
            f"Too many matches ({len(matched)}); refine find text "
            f"(max {_MAX_APPLY_ROWS} per apply)"
        )

    expenses_touched = 0
    fields_changed = 0
    touched_ids: list[int] = []

    for row in matched:
        changed = False
        new_merchant = _ci_replace(row.merchant or "", needle, replacement)
        if new_merchant != (row.merchant or ""):
            row.merchant = new_merchant
            fields_changed += 1
            changed = True
        new_note = _ci_replace(row.note or "", needle, replacement)
        if new_note != (row.note or ""):
            row.note = new_note
            fields_changed += 1
            changed = True
        if include_line_items:
            for item in row.line_items or []:
                new_desc = _ci_replace(item.description or "", needle, replacement)
                if new_desc != (item.description or ""):
                    item.description = new_desc
                    fields_changed += 1
                    changed = True
        if changed:
            expenses_touched += 1
            touched_ids.append(row.id)

    db.commit()

    for expense_id in touched_ids:
        refresh_duplicate_link(db, expense_id=expense_id)

    # Counts only — never log find/replace strings (sensitive).
    logger.info(
        "mass_rename applied",
        extra={
            "expenses_touched": expenses_touched,
            "fields_changed": fields_changed,
        },
    )
    return ApplyResult(
        expenses_touched=expenses_touched,
        fields_changed=fields_changed,
    )
