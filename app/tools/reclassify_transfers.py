"""CLI: reclassify family/savings bank transfers so Ask/Insights skip them.

Run inside the app container::

    python -m app.tools.reclassify_transfers
"""

from __future__ import annotations

import logging
import sys

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.services.transfers import reclassify_non_spend_transfers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("reclassify_transfers")


def main() -> int:
    """Entry point for ``python -m app.tools.reclassify_transfers``."""
    get_settings.cache_clear()
    init_db()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        n = reclassify_non_spend_transfers(db)
    logger.info("Updated %s expense rows to family/savings", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
