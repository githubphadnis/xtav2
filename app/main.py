"""xtav2 FastAPI application — mobile-first expense ledger."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db, init_db
from app.features import flag_snapshot, require_flag
from app.integrations.ollama import ask_ollama
from app.services import expenses as expense_service

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.app_log_level.upper(), logging.INFO))
logger = logging.getLogger("xtav2")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def today_iso(settings: Settings) -> str:
    """Local calendar date for the app timezone."""
    return datetime.now(ZoneInfo(settings.app_timezone)).date().isoformat()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Initialising database schema")
    init_db()
    yield


app = FastAPI(
    title="xtav2",
    description="Self-hosted multi-currency expense tracker (XTA reboot)",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> dict[str, object]:
    from sqlalchemy import text

    from app.db import get_engine

    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        logger.exception("Database health check failed")
        return {"status": "error", "detail": str(exc)}


@app.get("/health/flags")
def health_flags(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {"status": "ok", "flags": flag_snapshot(settings)}


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    rows = expense_service.list_expenses(db, limit=50) if settings.feature_manual_entry else []
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "expenses": rows,
            "settings": settings,
            "flags": flag_snapshot(settings),
            "today": today_iso(settings),
        },
    )


@app.post("/expenses")
def create_expense(
    spent_on: str = Form(...),
    amount: str = Form(...),
    currency: str = Form(...),
    merchant: str = Form(""),
    category: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not require_flag("FEATURE_MANUAL_ENTRY", settings):
        raise HTTPException(status_code=404, detail="Manual entry disabled")
    try:
        parsed_amount = Decimal(amount)
        parsed_date = date.fromisoformat(spent_on)
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid amount or date") from exc
    if parsed_amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    expense_service.add_expense(
        db,
        settings=settings,
        spent_on=parsed_date,
        amount=parsed_amount,
        currency=currency,
        merchant=merchant,
        category=category,
        note=note,
        source="manual",
    )
    return RedirectResponse(url="/", status_code=303)


@app.post("/ask", response_class=HTMLResponse)
async def ask(
    request: Request,
    question: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_OLLAMA_QA", settings):
        raise HTTPException(status_code=404, detail="Ollama Q&A disabled")

    # V1 heuristic: treat the question text as a filter needle + all-time sum.
    # Structured date parsing / text-to-SQL lands with FEATURE improvements.
    aggregate = expense_service.query_spend(db, settings=settings, q=question)
    system = (
        "You are xtav2, a concise expense assistant. Answer only from the provided "
        "aggregate JSON. If data is insufficient, say so. Prefer numbers and short sentences."
    )
    prompt = f"User question: {question}\nAggregate JSON: {aggregate}\nAnswer:"
    try:
        answer = await ask_ollama(settings, prompt, system)
    except Exception as exc:
        logger.exception("Ollama ask failed")
        answer = f"Could not reach Ollama ({exc}). Aggregate: {aggregate}"

    rows = expense_service.list_expenses(db, limit=50) if settings.feature_manual_entry else []
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "expenses": rows,
            "settings": settings,
            "flags": flag_snapshot(settings),
            "today": today_iso(settings),
            "question": question,
            "answer": answer,
            "aggregate": aggregate,
        },
    )
