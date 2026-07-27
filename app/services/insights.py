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
from app.models import Expense
from app.services.expenses import _exclude_active_duplicates, format_money

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


def today_in_tz(timezone: str) -> date:
    """Calendar today in the app timezone."""
    return datetime.now(ZoneInfo(timezone)).date()


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
    return InsightsPulse(
        currency=currency,
        this_month=this_month,
        last_month=last_month,
        delta=delta,
        delta_pct=delta_pct,
        delta_pct_label=delta_pct_label,
        categories=categories,
        merchants=merchants,
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
    """Width % for bar charts relative to the largest sibling (not grand total)."""
    if ceiling <= 0:
        return 0.0
    return round(float(total / ceiling * 100), 1)
