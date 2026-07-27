"""xtav2 FastAPI application — mobile-first expense ledger."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db, get_session_factory, init_db
from app.features import flag_snapshot, require_flag
from app.integrations.ollama import ask_ollama, list_models
from app.services import expenses as expense_service
from app.services import settings_store
from app.services.expenses import format_money
from app.services.receipts import (
    enqueue_receipt_upload,
    finalize_receipt_ocr,
    upload_root,
)

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.app_log_level.upper(), logging.INFO))
logger = logging.getLogger("xtav2")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["format_money"] = format_money


def today_iso(settings: Settings) -> str:
    """Local calendar date for the app timezone."""
    return datetime.now(ZoneInfo(settings.app_timezone)).date().isoformat()


def _page_context(
    *,
    request: Request,
    db: Session,
    settings: Settings,
    active: str,
    **extra: object,
) -> dict[str, object]:
    privacy = settings_store.privacy_local_only(db, settings)
    pending = (
        expense_service.list_pending(db, limit=20) if settings.feature_receipt_ocr else []
    )
    processing_count = (
        expense_service.count_expenses(db, status="processing")
        if settings.feature_receipt_ocr
        else 0
    )
    line_items_by_expense: dict[int, list] = {}
    if settings.feature_line_items:
        for e in pending:
            line_items_by_expense[e.id] = expense_service.list_line_items(
                db, expense_id=e.id
            )
    ctx: dict[str, object] = {
        "request": request,
        "active": active,
        "pending_count": len(pending),
        "processing_count": processing_count,
        "pending": pending,
        "line_items_by_expense": line_items_by_expense,
        "privacy_local_only": privacy,
        "google_vision_effective": settings_store.google_vision_allowed(db, settings),
        "google_key_configured": bool(settings.google_vision_api_key.strip()),
        "settings": settings,
        "flags": flag_snapshot(settings, db),
        "today": today_iso(settings),
    }
    ctx.update(extra)
    return ctx


async def _ocr_background(expense_id: int) -> None:
    try:
        warning = await finalize_receipt_ocr(expense_id=expense_id)
        if warning:
            logger.info("OCR finished for #%s with warning: %s", expense_id, warning)
        else:
            logger.info("OCR finished for #%s → pending", expense_id)
    except Exception:
        logger.exception("OCR background job failed for #%s", expense_id)


async def _requeue_stuck_processing() -> None:
    """After restart, resume OCR for rows still marked processing."""
    import asyncio

    await asyncio.sleep(1.5)
    try:
        SessionLocal = get_session_factory()
        with SessionLocal() as db:
            stuck = expense_service.list_processing(db, limit=100)
            ids = [row.id for row in stuck]
        for expense_id in ids:
            logger.info("Re-queueing stuck OCR job #%s", expense_id)
            await _ocr_background(expense_id)
    except Exception:
        logger.exception("Failed to requeue stuck OCR jobs")


@asynccontextmanager
async def lifespan(_: FastAPI):
    import asyncio

    logger.info("Initialising database schema")
    init_db()
    upload_root(settings)
    asyncio.create_task(_requeue_stuck_processing())
    yield


app = FastAPI(
    title="xtav2",
    description="Self-hosted multi-currency expense tracker (XTA reboot)",
    version="0.1.0",
    lifespan=lifespan,
)

uploads_path = upload_root(settings)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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
def health_flags(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return {"status": "ok", "flags": flag_snapshot(settings, db)}


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
    expenses = (
        expense_service.list_expenses(db, limit=50) if settings.feature_manual_entry else []
    )
    return templates.TemplateResponse(
        request,
        "ledger.html",
        _page_context(
            request=request,
            db=db,
            settings=settings,
            active="ledger",
            expenses=expenses,
        ),
    )


@app.get("/add", response_class=HTMLResponse)
def add_page(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_MANUAL_ENTRY", settings):
        raise HTTPException(status_code=404, detail="Manual entry disabled")
    return templates.TemplateResponse(
        request,
        "add.html",
        _page_context(request=request, db=db, settings=settings, active="add"),
    )


@app.get("/capture", response_class=HTMLResponse)
def capture_page(
    request: Request,
    queued: int | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_RECEIPT_OCR", settings):
        raise HTTPException(status_code=404, detail="Receipt capture disabled")
    flash = None
    if queued is not None:
        flash = (
            f"Queued #{queued} for OCR — keep scanning. "
            "It appears under Pending when parsing finishes."
        )
    return templates.TemplateResponse(
        request,
        "capture.html",
        _page_context(
            request=request,
            db=db,
            settings=settings,
            active="capture",
            flash=flash,
        ),
    )


@app.get("/pending", response_class=HTMLResponse)
def pending_page(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_RECEIPT_OCR", settings):
        raise HTTPException(status_code=404, detail="Receipt capture disabled")
    return templates.TemplateResponse(
        request,
        "pending.html",
        _page_context(request=request, db=db, settings=settings, active="pending"),
    )


@app.get("/ask", response_class=HTMLResponse)
def ask_page(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_OLLAMA_QA", settings):
        raise HTTPException(status_code=404, detail="Ollama Q&A disabled")
    return templates.TemplateResponse(
        request,
        "ask.html",
        _page_context(request=request, db=db, settings=settings, active="ask"),
    )


@app.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "settings.html",
        _page_context(request=request, db=db, settings=settings, active="settings"),
    )


@app.post("/settings/privacy")
def update_privacy(
    privacy_local_only: str | None = Form(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    # Checkbox present = on; absent = off
    enabled = privacy_local_only in {"1", "true", "on", "yes"}
    settings_store.set_privacy_local_only(db, enabled)
    return RedirectResponse(url="/settings", status_code=303)


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
    next: str = Form("/"),
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
    dest = next if next.startswith("/") else "/"
    return RedirectResponse(url=dest, status_code=303)


@app.post("/receipts/upload")
async def upload_receipt(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not require_flag("FEATURE_RECEIPT_OCR", settings):
        raise HTTPException(status_code=404, detail="Receipt capture disabled")
    data = await file.read()
    try:
        row = enqueue_receipt_upload(
            db,
            settings=settings,
            data=data,
            content_type=file.content_type or "",
            filename=file.filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(_ocr_background, row.id)
    return RedirectResponse(url=f"/capture?queued={row.id}", status_code=303)


@app.post("/expenses/{expense_id}/confirm")
def confirm_pending(
    expense_id: int,
    spent_on: str = Form(...),
    amount: str = Form(...),
    currency: str = Form(...),
    merchant: str = Form(""),
    category: str = Form(""),
    note: str = Form(""),
    item_description: list[str] = Form(default=[]),
    item_amount: list[str] = Form(default=[]),
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

    if settings.feature_line_items:
        items: list[dict[str, object]] = []
        for desc, amt in zip(item_description, item_amount, strict=False):
            d = (desc or "").strip()
            if not d:
                continue
            items.append({"description": d, "amount": amt or "0"})
        expense_service.replace_line_items(
            db, expense_id=expense_id, items=items, currency=currency
        )
    return RedirectResponse(url="/pending", status_code=303)


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
        "aggregate JSON. Prefer line_matches / line_total when the question is about a "
        "product (e.g. chocolate). If data is insufficient, say so. Prefer numbers and "
        "short sentences."
    )
    prompt = f"User question: {question}\nAggregate JSON: {aggregate}\nAnswer:"
    try:
        answer = await ask_ollama(settings, prompt, system)
    except Exception as exc:
        logger.exception("Ollama ask failed")
        answer = f"Could not reach Ollama ({exc}). Aggregate: {aggregate}"

    return templates.TemplateResponse(
        request,
        "ask.html",
        _page_context(
            request=request,
            db=db,
            settings=settings,
            active="ask",
            question=question,
            answer=answer,
            aggregate=aggregate,
        ),
    )
