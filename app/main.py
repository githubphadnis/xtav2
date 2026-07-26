"""xtav2 FastAPI application — mobile-first expense ledger."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db, init_db
from app.features import flag_snapshot, require_flag
from app.integrations.ollama import ask_ollama, list_models
from app.services import expenses as expense_service
from app.services.expenses import format_money
from app.services.receipts import create_pending_from_upload, upload_root

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.app_log_level.upper(), logging.INFO))
logger = logging.getLogger("xtav2")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["format_money"] = format_money


def today_iso(settings: Settings) -> str:
    """Local calendar date for the app timezone."""
    return datetime.now(ZoneInfo(settings.app_timezone)).date().isoformat()


def _page_context(
    *,
    db: Session,
    settings: Settings,
    **extra: object,
) -> dict[str, object]:
    ctx: dict[str, object] = {
        "expenses": (
            expense_service.list_expenses(db, limit=50) if settings.feature_manual_entry else []
        ),
        "pending": (
            expense_service.list_pending(db, limit=20) if settings.feature_receipt_ocr else []
        ),
        "settings": settings,
        "flags": flag_snapshot(settings),
        "today": today_iso(settings),
    }
    ctx.update(extra)
    return ctx


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Initialising database schema")
    init_db()
    upload_root(settings)
    yield


app = FastAPI(
    title="xtav2",
    description="Self-hosted multi-currency expense tracker (XTA reboot)",
    version="0.1.0",
    lifespan=lifespan,
)

uploads_path = upload_root(settings)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")


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


@app.get("/health/ollama")
async def health_ollama(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Probe Ollama /api/tags and report configured vs available models."""
    models = await list_models(settings)
    configured = settings.ollama_model
    ok = bool(models) and any(
        m == configured or m.startswith(f"{configured}:") for m in models
    )
    vision = (settings.ollama_vision_model or "").strip()
    vision_ok = bool(vision) and any(
        m == vision or m.startswith(f"{vision}:") for m in models
    )
    return {
        "status": "ok" if ok else "misconfigured",
        "base_url": settings.ollama_base_url,
        "configured_model": configured,
        "vision_model": vision or None,
        "vision_model_available": vision_ok,
        "available_models": models,
        "reachable": bool(models),
    }


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "home.html", _page_context(db=db, settings=settings)
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


@app.post("/expenses/{expense_id}/delete")
def remove_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not (
        require_flag("FEATURE_MANUAL_ENTRY", settings)
        or require_flag("FEATURE_RECEIPT_OCR", settings)
    ):
        raise HTTPException(status_code=404, detail="Delete disabled")
    deleted = expense_service.delete_expense(db, expense_id=expense_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")
    return RedirectResponse(url="/", status_code=303)


@app.post("/receipts/upload")
async def upload_receipt(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_RECEIPT_OCR", settings):
        raise HTTPException(status_code=404, detail="Receipt capture disabled")
    data = await file.read()
    try:
        row, warning = await create_pending_from_upload(
            db,
            settings=settings,
            data=data,
            content_type=file.content_type or "",
            filename=file.filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    flash = f"Receipt saved as pending #{row.id}."
    if warning:
        flash = f"{flash} OCR skipped: {warning}"
    return templates.TemplateResponse(
        request,
        "home.html",
        _page_context(db=db, settings=settings, flash=flash),
    )


@app.post("/expenses/{expense_id}/confirm")
def confirm_pending(
    expense_id: int,
    spent_on: str = Form(...),
    amount: str = Form(...),
    currency: str = Form(...),
    merchant: str = Form(""),
    category: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not require_flag("FEATURE_RECEIPT_OCR", settings):
        raise HTTPException(status_code=404, detail="Receipt capture disabled")
    try:
        parsed_amount = Decimal(amount)
        parsed_date = date.fromisoformat(spent_on)
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid amount or date") from exc
    if parsed_amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    updated = expense_service.update_expense(
        db,
        settings=settings,
        expense_id=expense_id,
        spent_on=parsed_date,
        amount=parsed_amount,
        currency=currency,
        merchant=merchant,
        category=category,
        note=note,
        status="posted",
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Expense not found")
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

    return templates.TemplateResponse(
        request,
        "home.html",
        _page_context(
            db=db,
            settings=settings,
            question=question,
            answer=answer,
            aggregate=aggregate,
        ),
    )
