"""xtav2 FastAPI application — mobile-first expense ledger."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote
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
from app.integrations.ollama import list_models
from app.services import expenses as expense_service
from app.services import settings_store
from app.services.duplicates import count_active_duplicates, dismiss_duplicate
from app.services.expenses import format_money
from app.services.fx import COMMON_CURRENCIES, fx_health
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
templates.env.filters["urlencode"] = lambda value: quote(str(value), safe="")


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
        "currencies": list(COMMON_CURRENCIES),
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
            from app.services.duplicates import rescan_all_duplicates

            n = rescan_all_duplicates(db, limit=500)
            logger.info("Duplicate rescan touched %s expenses", n)
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


@app.get("/health/fx")
def health_fx(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Probe FX API when multi-currency is enabled."""
    if not settings.feature_multi_currency:
        return {"status": "disabled", "reachable": False}
    return fx_health(settings)


@app.get("/health/spend-summary")
def health_spend_summary(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Operator snapshot: posted counts and top merchants (no secrets)."""
    return {
        "status": "ok",
        "posted": expense_service.count_expenses(db, status="posted"),
        "pending": expense_service.count_expenses(db, status="pending"),
        "processing": expense_service.count_expenses(db, status="processing"),
        "empty_merchant_count": expense_service.count_empty_merchants(db),
        "active_duplicates": count_active_duplicates(db),
        "merchant_breakdown": expense_service.merchant_breakdown(db, settings=settings),
    }


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
    category: str | None = None,
    merchant: str | None = None,
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    start_d: date | None = None
    end_d: date | None = None
    try:
        if start:
            start_d = date.fromisoformat(start)
        if end:
            end_d = date.fromisoformat(end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date filter") from exc

    expenses = (
        expense_service.list_expenses(
            db,
            limit=50,
            category=category,
            merchant=merchant,
            start=start_d,
            end=end_d,
        )
        if settings.feature_manual_entry
        else []
    )
    filter_bits = []
    if category:
        filter_bits.append(f"category={category}")
    if merchant:
        filter_bits.append(f"merchant={merchant}")
    if start_d:
        filter_bits.append(f"from {start_d}")
    if end_d:
        filter_bits.append(f"to {end_d}")
    filter_label = " · ".join(filter_bits) if filter_bits else None
    return templates.TemplateResponse(
        request,
        "ledger.html",
        _page_context(
            request=request,
            db=db,
            settings=settings,
            active="ledger",
            expenses=expenses,
            filter_label=filter_label,
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
    flash: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_RECEIPT_OCR", settings):
        raise HTTPException(status_code=404, detail="Receipt capture disabled")
    return templates.TemplateResponse(
        request,
        "pending.html",
        _page_context(
            request=request,
            db=db,
            settings=settings,
            active="pending",
            flash=flash,
        ),
    )


@app.get("/ask", response_class=HTMLResponse)
def ask_page(
    request: Request,
    q: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_OLLAMA_QA", settings):
        raise HTTPException(status_code=404, detail="Ollama Q&A disabled")
    return templates.TemplateResponse(
        request,
        "ask.html",
        _page_context(
            request=request,
            db=db,
            settings=settings,
            active="ask",
            question=q or "",
        ),
    )


@app.get("/insights", response_class=HTMLResponse)
def insights_page(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_TRENDS_UI", settings):
        raise HTTPException(status_code=404, detail="Insights disabled")
    from app.services.insights import bar_share, build_pulse, format_delta, key_message

    pulse = build_pulse(db, settings=settings)
    cat_ceiling = max((c.total for c in pulse.categories), default=Decimal(0))
    merch_ceiling = max((m.total for m in pulse.merchants), default=Decimal(0))
    trend_ceiling = max((m.total for m in pulse.trend_months), default=Decimal("0.01"))
    return templates.TemplateResponse(
        request,
        "insights.html",
        _page_context(
            request=request,
            db=db,
            settings=settings,
            active="insights",
            pulse=pulse,
            format_delta=format_delta,
            key_message=key_message(pulse),
            bar_share=bar_share,
            cat_ceiling=cat_ceiling,
            merch_ceiling=merch_ceiling,
            trend_ceiling=trend_ceiling,
        ),
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


@app.get("/bank", response_class=HTMLResponse)
def bank_page(
    request: Request,
    flash: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_BANK_IMPORT", settings):
        raise HTTPException(status_code=404, detail="Bank import disabled")
    return templates.TemplateResponse(
        request,
        "bank.html",
        _page_context(
            request=request,
            db=db,
            settings=settings,
            active="settings",
            flash=flash,
        ),
    )


@app.post("/bank/import")
async def bank_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not require_flag("FEATURE_BANK_IMPORT", settings):
        raise HTTPException(status_code=404, detail="Bank import disabled")
    from urllib.parse import quote

    from app.services.bank_import import import_bank_csv

    data = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail="File too large")
    result = import_bank_csv(
        db,
        settings=settings,
        data=data,
        filename=file.filename or "statement.csv",
    )
    if result.errors:
        msg = result.errors[0]
    else:
        msg = (
            f"Parsed {result.parsed}: created {result.created}, "
            f"linked {result.linked}, skipped {result.skipped_existing}."
        )
    return RedirectResponse(url=f"/bank?flash={quote(msg)}", status_code=303)


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
    fx_rate: str = Form(""),
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

    rate_override: Decimal | None = None
    if fx_rate.strip():
        try:
            rate_override = Decimal(fx_rate.replace(",", "."))
            if rate_override <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid FX rate") from exc

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
        fx_rate_override=rate_override,
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


@app.post("/expenses/{expense_id}/dismiss-duplicate")
def dismiss_duplicate_expense(
    expense_id: int,
    next: str = Form("/"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not (
        require_flag("FEATURE_MANUAL_ENTRY", settings)
        or require_flag("FEATURE_RECEIPT_OCR", settings)
    ):
        raise HTTPException(status_code=404, detail="Dismiss disabled")
    row = dismiss_duplicate(db, expense_id=expense_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    dest = next if next.startswith("/") else "/"
    return RedirectResponse(url=dest, status_code=303)


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

    from urllib.parse import quote

    from app.services.confirm_receipt import confirm_receipt_expense

    items: list[dict[str, object]] = []
    if settings.feature_line_items:
        for desc, amt in zip(item_description, item_amount, strict=False):
            d = (desc or "").strip()
            if not d:
                continue
            items.append({"description": d, "amount": amt or "0"})

    updated, flash = confirm_receipt_expense(
        db,
        settings=settings,
        expense_id=expense_id,
        spent_on=parsed_date,
        amount=parsed_amount,
        currency=currency,
        merchant=merchant,
        category=category,
        note=note,
        line_items=items,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return RedirectResponse(
        url=f"/pending?flash={quote(flash)}",
        status_code=303,
    )


@app.post("/ask", response_class=HTMLResponse)
async def ask(
    request: Request,
    question: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    if not require_flag("FEATURE_OLLAMA_QA", settings):
        raise HTTPException(status_code=404, detail="Ollama Q&A disabled")

    from app.services.ask_agent import answer_question

    answer, aggregate = await answer_question(db, settings, question=question)

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
