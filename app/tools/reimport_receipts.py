"""CLI: wipe expenses and re-OCR receipt images from UPLOAD_DIR (#24).

Run inside the app container (Portainer console or docker exec)::

    python -m app.tools.reimport_receipts --dry-run
    python -m app.tools.reimport_receipts --wipe --ocr --yes

Keeps the uploads volume; deletes all expense rows. Confirm Pending dates after OCR.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.services.reimport import reimport_receipts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("reimport")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wipe expenses and re-queue receipt images for OCR (#24)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List upload images only; do not wipe or enqueue",
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete all expenses and line items before enqueue",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Run OCR on each enqueued row (→ pending)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required with --wipe to confirm destructive action",
    )
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    if args.wipe and not args.yes and not args.dry_run:
        logger.error("Refusing --wipe without --yes (destructive).")
        return 2
    if not args.dry_run and not args.wipe:
        logger.error("Pass --wipe (with --yes) or --dry-run. Nothing to do.")
        return 2

    get_settings.cache_clear()
    settings = get_settings()
    init_db()
    SessionLocal = get_session_factory()

    with SessionLocal() as db:
        result = await reimport_receipts(
            db,
            settings=settings,
            wipe=bool(args.wipe and not args.dry_run),
            run_ocr=bool(args.ocr and not args.dry_run),
            dry_run=bool(args.dry_run),
        )

    logger.info(
        "Reimport done: wiped=%s files=%s enqueued=%s ocr_done=%s",
        result.wiped,
        result.files_found,
        result.enqueued,
        result.ocr_done,
    )
    for warning in result.ocr_warnings:
        logger.warning("OCR: %s", warning)
    for skip in result.skipped:
        logger.warning("Skip: %s", skip)
    if result.enqueued and args.ocr:
        logger.info("Review Pending in the UI — confirm printed Datum before posting.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m app.tools.reimport_receipts``."""
    args = _parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
