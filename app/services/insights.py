"""Insights Phase 1 — MoM pulse + category/merchant breakdowns (Postgres only)."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Expense, ExpenseLineItem
from app.services.expenses import _exclude_active_duplicates, _exclude_non_spend, format_money

_MONEY_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class PeriodTotal:
    """Spend total for a date window."""

    label: str
    start: date
    end: date
    total: Decimal
    count: int
    currency: str


@dataclass(frozen=True)
class BreakdownRow:
    """One category or merchant slice."""

    key: str
    total: Decimal
    count: int
    pct: float
    currency: str


@dataclass(frozen=True)
class LineItemInsightRow:
    """One frequently bought line-item description."""

    key: str
    count: int
    total: Decimal
    average: Decimal
    currency: str


@dataclass(frozen=True)
class InsightsPulse:
    """Phase 1 Insights payload for the UI."""

    currency: str
    this_month: PeriodTotal
    last_month: PeriodTotal
    delta: Decimal
    delta_pct: float | None
    delta_pct_label: str
    categories: list[BreakdownRow]
    merchants: list[BreakdownRow]
    top_shops: list[BreakdownRow]
    top_shops_start: date
    top_line_items: list[LineItemInsightRow]
    top_line_items_start: date
    trend_months: list[PeriodTotal]


def today_in_tz(timezone: str) -> date:
    """Calendar today in the app timezone."""
    return datetime.now(ZoneInfo(timezone)).date()


def _add_months(first_of_month: date, delta_months: int) -> date:
    """Shift a first-of-month date by delta_months (may be negative)."""
    year = first_of_month.year
    month = first_of_month.month + delta_months
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def month_span(first: date, today: date) -> tuple[date, date]:
    """Inclusive [start, end] for a calendar month; current month is MTD."""
    last_day = monthrange(first.year, first.month)[1]
    end = date(first.year, first.month, last_day)
    if first.year == today.year and first.month == today.month:
        end = today
    return first, end


def rolling_month_windows(today: date, *, months: int = 3) -> list[tuple[date, date, str]]:
    """Oldest→newest rolling months (current = MTD)."""
    n = max(1, min(months, 12))
    this_first = today.replace(day=1)
    out: list[tuple[date, date, str]] = []
    for back in range(n - 1, -1, -1):
        first = _add_months(this_first, -back)
        start, end = month_span(first, today)
        out.append((start, end, first.strftime("%b")))
    return out


def month_windows(today: date) -> tuple[date, date, date, date]:
    """Return (this_start, this_end, last_start, last_end) with like-for-like MTD.

    Last window ends on the same day-of-month when possible (capped by month length),
    so MoM is not full-month vs partial-month.
    """
    this_start = today.replace(day=1)
    this_end = today
    if this_start.month == 1:
        last_start = date(this_start.year - 1, 12, 1)
    else:
        last_start = date(this_start.year, this_start.month - 1, 1)
    last_month_len = monthrange(last_start.year, last_start.month)[1]
    last_end = date(
        last_start.year,
        last_start.month,
        min(today.day, last_month_len),
    )
    return this_start, this_end, last_start, last_end


def _amount_col(settings: Settings):
    return Expense.amount_base if settings.feature_multi_currency else Expense.amount


def _currency_label(settings: Settings) -> str:
    if settings.feature_multi_currency:
        return settings.base_currency.upper()
    return "mixed"


def period_total(
    db: Session,
    *,
    settings: Settings,
    start: date,
    end: date,
    label: str,
) -> PeriodTotal:
    """Sum posted spend in [start, end] — same exclusion rules as query_spend."""
    amount_col = _amount_col(settings)
    stmt = select(
        func.coalesce(func.sum(amount_col), 0),
        func.count(Expense.id),
    ).where(
        Expense.status == "posted",
        _exclude_active_duplicates(),
        _exclude_non_spend(),
        Expense.spent_on >= start,
        Expense.spent_on <= end,
    )
    total_raw, count = db.execute(stmt).one()
    total = Decimal(str(total_raw or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    return PeriodTotal(
        label=label,
        start=start,
        end=end,
        total=total,
        count=int(count or 0),
        currency=_currency_label(settings),
    )


def _breakdown(
    db: Session,
    *,
    settings: Settings,
    start: date,
    end: date,
    group_col,
    empty_label: str,
    limit: int = 8,
) -> list[BreakdownRow]:
    amount_col = _amount_col(settings)
    label_expr = func.nullif(func.trim(group_col), "")
    stmt = (
        select(
            label_expr,
            func.coalesce(func.sum(amount_col), 0),
            func.count(Expense.id),
        )
        .where(
            Expense.status == "posted",
            _exclude_active_duplicates(),
            _exclude_non_spend(),
            Expense.spent_on >= start,
            Expense.spent_on <= end,
        )
        .group_by(label_expr)
        .order_by(func.sum(amount_col).desc())
        .limit(limit)
    )
    rows = list(db.execute(stmt).all())
    currency = _currency_label(settings)
    grand = sum(
        (Decimal(str(t or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP) for _, t, _ in rows),
        Decimal("0.00"),
    )
    out: list[BreakdownRow] = []
    for key, total_raw, count in rows:
        total = Decimal(str(total_raw or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        pct = float((total / grand * 100) if grand > 0 else 0)
        out.append(
            BreakdownRow(
                key=(key or empty_label),
                total=total,
                count=int(count or 0),
                pct=round(pct, 1),
                currency=currency,
            )
        )
    return out


def _shops_by_visits(
    db: Session,
    *,
    settings: Settings,
    start: date,
    end: date,
    limit: int = 5,
) -> list[BreakdownRow]:
    """Top shops by visit count (expense rows), with spend totals for bar labels."""
    amount_col = _amount_col(settings)
    label_expr = func.nullif(func.trim(Expense.merchant), "")
    stmt = (
        select(
            label_expr,
            func.coalesce(func.sum(amount_col), 0),
            func.count(Expense.id),
        )
        .where(
            Expense.status == "posted",
            _exclude_active_duplicates(),
            _exclude_non_spend(),
            Expense.spent_on >= start,
            Expense.spent_on <= end,
        )
        .group_by(label_expr)
        .order_by(func.count(Expense.id).desc(), func.sum(amount_col).desc())
        .limit(limit)
    )
    rows = list(db.execute(stmt).all())
    currency = _currency_label(settings)
    visit_ceiling = max((int(c or 0) for _, _, c in rows), default=0)
    out: list[BreakdownRow] = []
    for key, total_raw, count in rows:
        total = Decimal(str(total_raw or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        visits = int(count or 0)
        pct = float((visits / visit_ceiling * 100) if visit_ceiling > 0 else 0)
        out.append(
            BreakdownRow(
                key=(key or "unknown merchant"),
                total=total,
                count=visits,
                pct=round(pct, 1),
                currency=currency,
            )
        )
    return out


def _top_line_items(
    db: Session,
    *,
    settings: Settings,
    start: date,
    end: date,
    limit: int = 10,
) -> list[LineItemInsightRow]:
    """Top bought line descriptions by frequency; average line amount."""
    label_expr = func.nullif(func.trim(ExpenseLineItem.description), "")
    # Line amounts are stored in original currency; prefer amount_base on parent
    # when multi-currency by scaling is not available per line — use line amount
    # and report base currency label only when all lines share base (V1: EUR lines).
    amount_expr = ExpenseLineItem.amount
    stmt = (
        select(
            label_expr,
            func.count(ExpenseLineItem.id),
            func.coalesce(func.sum(amount_expr), 0),
            func.coalesce(func.avg(amount_expr), 0),
        )
        .join(Expense, Expense.id == ExpenseLineItem.expense_id)
        .where(
            Expense.status == "posted",
            _exclude_active_duplicates(),
            _exclude_non_spend(),
            Expense.spent_on >= start,
            Expense.spent_on <= end,
            label_expr.is_not(None),
        )
        .group_by(label_expr)
        .order_by(func.count(ExpenseLineItem.id).desc(), func.sum(amount_expr).desc())
        .limit(limit)
    )
    rows = list(db.execute(stmt).all())
    currency = _currency_label(settings)
    out: list[LineItemInsightRow] = []
    for key, count, total_raw, avg_raw in rows:
        total = Decimal(str(total_raw or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        average = Decimal(str(avg_raw or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        out.append(
            LineItemInsightRow(
                key=str(key),
                count=int(count or 0),
                total=total,
                average=average,
                currency=currency,
            )
        )
    return out


def build_pulse(db: Session, *, settings: Settings, today: date | None = None) -> InsightsPulse:
    """Build Phase 1 Insights aggregates for the Insights screen."""
    day = today or today_in_tz(settings.app_timezone)
    this_start, this_end, last_start, last_end = month_windows(day)
    currency = _currency_label(settings)

    this_month = period_total(
        db,
        settings=settings,
        start=this_start,
        end=this_end,
        label=this_start.strftime("%b %Y"),
    )
    last_month = period_total(
        db,
        settings=settings,
        start=last_start,
        end=last_end,
        label=last_start.strftime("%b %Y"),
    )
    delta = this_month.total - last_month.total
    delta_pct: float | None
    delta_pct_label = ""
    if last_month.total > 0:
        delta_pct = round(float(delta / last_month.total * 100), 1)
        delta_pct_label = f"{delta_pct:+.1f}%"
    elif this_month.total > 0:
        delta_pct = None  # no baseline
    else:
        delta_pct = 0.0
        delta_pct_label = "0.0%"

    categories = _breakdown(
        db,
        settings=settings,
        start=this_start,
        end=this_end,
        group_col=Expense.category,
        empty_label="uncategorized",
    )
    merchants = _breakdown(
        db,
        settings=settings,
        start=this_start,
        end=this_end,
        group_col=Expense.merchant,
        empty_label="unknown merchant",
    )
    shops_start = rolling_month_windows(day, months=3)[0][0]
    lines_start = rolling_month_windows(day, months=6)[0][0]
    top_shops = _shops_by_visits(
        db,
        settings=settings,
        start=shops_start,
        end=this_end,
        limit=5,
    )
    top_line_items: list[LineItemInsightRow] = []
    if settings.feature_line_items:
        top_line_items = _top_line_items(
            db,
            settings=settings,
            start=lines_start,
            end=this_end,
            limit=10,
        )
    trend_months: list[PeriodTotal] = []
    for start, end, short_label in rolling_month_windows(day, months=3):
        trend_months.append(
            period_total(
                db, settings=settings, start=start, end=end, label=short_label
            )
        )
    return InsightsPulse(
        currency=currency,
        this_month=this_month,
        last_month=last_month,
        delta=delta,
        delta_pct=delta_pct,
        delta_pct_label=delta_pct_label,
        categories=categories,
        merchants=merchants,
        top_shops=top_shops,
        top_shops_start=shops_start,
        top_line_items=top_line_items,
        top_line_items_start=lines_start,
        trend_months=trend_months,
    )


def format_delta(delta: Decimal, currency: str) -> str:
    """Human delta string with sign."""
    sign = "+" if delta > 0 else ""
    return f"{sign}{format_money(delta)} {currency}"


def key_message(pulse: InsightsPulse) -> str:
    """One-line MoM comparator for the Insights hero."""
    cur = pulse.currency
    if pulse.this_month.total == 0 and pulse.last_month.total == 0:
        return "No posted spend in either window yet."
    if pulse.delta > 0:
        return (
            f"You spent {format_money(pulse.delta)} {cur} more this month "
            f"than the same days last month."
        )
    if pulse.delta < 0:
        return (
            f"You spent {format_money(abs(pulse.delta))} {cur} less this month "
            f"than the same days last month."
        )
    return "Spend matches the same days last month."


def bar_share(total: Decimal, ceiling: Decimal) -> float:
    """Width/height % relative to the largest sibling (not grand total)."""
    if ceiling <= 0:
        return 0.0
    return round(float(total / ceiling * 100), 1)


def bar_height_rem(total: Decimal, ceiling: Decimal, *, max_rem: float = 8.0) -> float:
    """Absolute rem height for vertical bars (CSS % height collapses without fixed parent)."""
    share = bar_share(total, ceiling)
    # Keep a visible stub for zero so the column layout stays readable.
    if share <= 0:
        return 0.25
    return round(max(0.35, max_rem * share / 100.0), 2)
