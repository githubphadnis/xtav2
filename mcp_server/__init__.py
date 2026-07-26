"""MCP server entrypoint for xtav2 (FEATURE_MCP).

Uses the official MCP Python SDK when installed. Tools call the same domain
services as the HTTP API.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.db import get_session_factory, init_db
from app.features import flag_snapshot, require_flag
from app.services import expenses as expense_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("xtav2.mcp")

settings = get_settings()
mcp = FastMCP("xtav2")


def _ensure_ready() -> None:
    if not require_flag("FEATURE_MCP", settings):
        raise RuntimeError("FEATURE_MCP is disabled")
    init_db()


@mcp.tool()
def list_feature_flags() -> dict[str, bool]:
    """List all FEATURE_* flags and whether each module is enabled."""
    _ensure_ready()
    return flag_snapshot(settings)


@mcp.tool()
def add_expense(
    amount: float,
    currency: str,
    spent_on: str,
    merchant: str = "",
    category: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Add a manual expense. spent_on is ISO date (YYYY-MM-DD)."""
    _ensure_ready()
    if not require_flag("FEATURE_MANUAL_ENTRY", settings):
        raise RuntimeError("FEATURE_MANUAL_ENTRY is disabled")
    try:
        parsed_amount = Decimal(str(amount))
        parsed_date = date.fromisoformat(spent_on)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid amount or spent_on") from exc

    with get_session_factory()() as db:
        row = expense_service.add_expense(
            db,
            settings=settings,
            spent_on=parsed_date,
            amount=parsed_amount,
            currency=currency,
            merchant=merchant,
            category=category,
            note=note,
            source="mcp",
        )
        return {
            "id": row.id,
            "spent_on": row.spent_on.isoformat(),
            "amount": float(row.amount),
            "currency": row.currency,
            "merchant": row.merchant,
            "category": row.category,
        }


@mcp.tool()
def delete_expense(expense_id: int) -> dict[str, Any]:
    """Delete an expense by id. Returns whether a row was removed."""
    _ensure_ready()
    if not require_flag("FEATURE_MANUAL_ENTRY", settings):
        raise RuntimeError("FEATURE_MANUAL_ENTRY is disabled")
    with get_session_factory()() as db:
        deleted = expense_service.delete_expense(db, expense_id=expense_id)
        return {"id": expense_id, "deleted": deleted}


@mcp.tool()
def list_expenses(limit: int = 20, q: str | None = None) -> list[dict[str, Any]]:
    """List recent expenses, optionally filtered by free-text q."""
    _ensure_ready()
    with get_session_factory()() as db:
        rows = expense_service.list_expenses(db, limit=limit, q=q)
        return [
            {
                "id": r.id,
                "spent_on": r.spent_on.isoformat(),
                "amount": float(r.amount),
                "currency": r.currency,
                "merchant": r.merchant,
                "category": r.category,
                "note": r.note,
            }
            for r in rows
        ]


@mcp.tool()
def query_spend(
    q: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Sum spend for an optional text filter and ISO date window."""
    _ensure_ready()
    start_d = date.fromisoformat(start) if start else None
    end_d = date.fromisoformat(end) if end else None
    with get_session_factory()() as db:
        return expense_service.query_spend(
            db, settings=settings, start=start_d, end=end_d, q=q
        )


def main() -> None:
    if not settings.feature_mcp:
        logger.error("FEATURE_MCP=false — refusing to start MCP server")
        raise SystemExit(1)
    logger.info("Starting xtav2 MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
