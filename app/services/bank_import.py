"""Bank statement import orchestration behind FEATURE_BANK_IMPORT."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings
from app.services import expenses as expense_service
from app.services.bank_csv import BankRow, parse_bank_csv
from app.services.reconcile import (
    attach_bank_ref_to_expense,
    find_expense_by_bank_ref,
    find_reconcile_candidates,
)
from app.services.transfers import classify_transfer_category, reclassify_non_spend_transfers

logger = logging.getLogger("xtav2.bank_import")


@dataclass
class ImportResult:
    """Summary of a CSV import run."""

    parsed: int = 0
    created: int = 0
    linked: int = 0
    skipped_existing: int = 0
    errors: list[str] | None = None


def import_bank_csv(
    db: Session,
    *,
    settings: Settings,
    data: bytes,
    filename: str,
) -> ImportResult:
    """Import bank CSV: create bank expenses or link to matching receipt rows."""
    result = ImportResult(errors=[])
    try:
        rows = parse_bank_csv(
            data,
            default_currency=settings.base_currency.upper(),
            filename=filename or "statement.csv",
        )
    except ValueError as exc:
        result.errors = [str(exc)]
        return result

    result.parsed = len(rows)
    for row in rows:
        _import_one(db, settings=settings, row=row, result=result)

    # Tag existing + new transfer rows (Rashmi / pocket) so Ask/Insights skip them.
    reclassified = reclassify_non_spend_transfers(db)
    if reclassified:
        logger.info("Reclassified %s non-spend transfer rows", reclassified)

    logger.info(
        "Bank import %s: parsed=%s created=%s linked=%s skipped=%s",
        filename,
        result.parsed,
        result.created,
        result.linked,
        result.skipped_existing,
    )
    return result


def _import_one(
    db: Session,
    *,
    settings: Settings,
    row: BankRow,
    result: ImportResult,
) -> None:
    existing_ref = find_expense_by_bank_ref(db, bank_ref=row.bank_ref)
    if existing_ref is not None:
        result.skipped_existing += 1
        return

    candidates = find_reconcile_candidates(
        db,
        spent_on=row.spent_on,
        amount=row.amount,
        merchant=row.merchant,
        currency=row.currency,
        prefer_sources=("receipt", "manual", "receipt+bank", "bank+receipt"),
    )
    # Prefer a candidate that already has receipt detail and no bank_ref yet.
    match = None
    for cand in candidates:
        if cand.bank_ref:
            continue
        if cand.source.startswith("bank") and "receipt" not in cand.source:
            continue
        match = cand
        break
    if match is None:
        for cand in candidates:
            if not cand.bank_ref:
                match = cand
                break

    if match is not None:
        attach_bank_ref_to_expense(
            db,
            expense=match,
            bank_ref=row.bank_ref,
            bank_note=row.note,
        )
        result.linked += 1
        return

    expense_service.add_expense(
        db,
        settings=settings,
        spent_on=row.spent_on,
        amount=row.amount,
        currency=row.currency,
        merchant=row.merchant,
        category=classify_transfer_category(row.merchant, row.note) or "",
        note=row.note,
        source="bank",
        status="posted",
        bank_ref=row.bank_ref,
    )
    result.created += 1
