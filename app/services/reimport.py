"""Operator helpers: wipe expenses and re-queue receipt images from UPLOAD_DIR (#24)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Expense, ExpenseLineItem
from app.services import expenses as expense_service
from app.services.receipts import finalize_receipt_ocr, upload_root

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


@dataclass(frozen=True)
class ReimportResult:
    """Summary of a wipe + reimport run."""

    wiped: int
    files_found: int
    enqueued: int
    ocr_done: int
    ocr_warnings: list[str]
    skipped: list[str]


def list_receipt_images(settings: Settings) -> list[str]:
    """Return relative filenames under upload_dir (sorted)."""
    root = upload_root(settings)
    names: list[str] = []
    for path in sorted(root.iterdir()):
        if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES:
            names.append(path.name)
    return names


def wipe_all_expenses(db: Session) -> int:
    """Delete all expenses and line items. Keeps app_settings and upload files."""
    # Clear self-FK first so Postgres accepts bulk delete.
    db.query(Expense).update(
        {Expense.duplicate_of_id: None},
        synchronize_session=False,
    )
    db.query(ExpenseLineItem).delete(synchronize_session=False)
    deleted = db.query(Expense).delete(synchronize_session=False)
    db.commit()
    logger.warning("Wiped %s expense rows (line items cascade-cleared)", deleted)
    return int(deleted)


def enqueue_existing_receipt(
    db: Session,
    *,
    settings: Settings,
    relative_path: str,
) -> Expense:
    """Create a processing row pointing at an existing upload file (no copy)."""
    relative = Path(relative_path).name
    path = upload_root(settings) / relative
    if not path.is_file():
        raise FileNotFoundError(f"Receipt file missing: {relative}")
    today = datetime.now(ZoneInfo(settings.app_timezone)).date()
    return expense_service.add_expense(
        db,
        settings=settings,
        spent_on=today,
        amount=Decimal("0.00"),
        currency=settings.base_currency.upper(),
        merchant="",
        category="receipt",
        note="ocr:reimport",
        source="receipt",
        status="processing",
        receipt_path=relative,
    )


async def reimport_receipts(
    db: Session,
    *,
    settings: Settings,
    wipe: bool,
    run_ocr: bool,
    dry_run: bool = False,
) -> ReimportResult:
    """Wipe expenses (optional) and re-enqueue every image in UPLOAD_DIR for OCR.

    Leaves rows as ``pending`` after OCR so the operator can confirm printed dates.
    Does **not** remove files from the uploads volume.
    """
    files = list_receipt_images(settings)
    skipped: list[str] = []
    warnings: list[str] = []

    if dry_run:
        return ReimportResult(
            wiped=0,
            files_found=len(files),
            enqueued=0,
            ocr_done=0,
            ocr_warnings=[],
            skipped=[f"dry-run: would process {name}" for name in files],
        )

    wiped = 0
    if wipe:
        wiped = wipe_all_expenses(db)

    ids: list[int] = []
    for name in files:
        try:
            row = enqueue_existing_receipt(db, settings=settings, relative_path=name)
            ids.append(row.id)
        except FileNotFoundError as exc:
            skipped.append(str(exc))
            logger.warning("%s", exc)

    ocr_done = 0
    if run_ocr:
        for expense_id in ids:
            warning = await finalize_receipt_ocr(expense_id=expense_id)
            ocr_done += 1
            if warning:
                warnings.append(f"#{expense_id}: {warning}")
                logger.info("Reimport OCR #%s warning: %s", expense_id, warning)
            else:
                logger.info("Reimport OCR #%s → pending", expense_id)

    return ReimportResult(
        wiped=wiped,
        files_found=len(files),
        enqueued=len(ids),
        ocr_done=ocr_done,
        ocr_warnings=warnings,
        skipped=skipped,
    )
