"""Expense domain services — shared by HTTP and MCP."""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Expense, ExpenseLineItem

logger = logging.getLogger("xtav2.expenses")

_MONEY_QUANT = Decimal("0.01")
_STOPWORDS = frozenset(
    {
        "how",
        "much",
        "did",
        "i",
        "spend",
        "spent",
        "at",
        "on",
        "in",
        "the",
        "a",
        "an",
        "this",
        "that",
        "year",
        "month",
        "week",
        "quarter",
        "last",
        "what",
        "when",
        "where",
        "was",
        "were",
        "for",
        "from",
        "with",
        "about",
        "total",
        "all",
        "my",
        "me",
        "to",
        "of",
        "and",
        "or",
        "tis",
        # visit / count question noise
        "many",
        "times",
        "go",
        "went",
        "often",
        "visit",
        "visits",
        "shop",
        "shops",
        "have",
        "has",
        "get",
        "got",
    }
)

# Natural-language → category filter (e.g. "the shops" = groceries).
_CATEGORY_ALIASES: dict[str, str] = {
    "shop": "groceries",
    "shops": "groceries",
    "supermarket": "groceries",
    "supermarkets": "groceries",
    "grocery": "groceries",
    "groceries": "groceries",
}

# Product Ask: English/German variants for line-item matching.
_PRODUCT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "kebab": ("kebab", "kebap", "kebabs", "döner", "doner", "doener", "dönerkebab"),
    "kebap": ("kebab", "kebap", "kebabs", "döner", "doner", "doener"),
    "kebabs": ("kebab", "kebap", "kebabs", "döner", "doner", "doener"),
    "doner": ("kebab", "kebap", "döner", "doner", "doener"),
    "doener": ("kebab", "kebap", "döner", "doner", "doener"),
    "döner": ("kebab", "kebap", "döner", "doner", "doener"),
    "chocolate": ("chocolate", "schokolade", "schoko", "kakao"),
    "schokolade": ("chocolate", "schokolade", "schoko"),
    "milk": ("milk", "milch"),
    "milch": ("milk", "milch"),
    "coffee": ("coffee", "kaffee"),
    "kaffee": ("coffee", "kaffee"),
    "bread": ("bread", "brot", "brötchen", "brotchen"),
    "beer": ("beer", "bier"),
    "wine": ("wine", "wein"),
}


def format_money(amount: Decimal | float | str) -> str:
    """Format amounts for UI as two decimal places."""
    value = Decimal(str(amount)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    return f"{value:.2f}"


def expand_product_tokens(tokens: list[str]) -> list[str]:
    """Expand tokens with product synonyms for line-item / note matching."""
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        key = token.lower()
        variants = _PRODUCT_SYNONYMS.get(key, (token,))
        for variant in variants:
            low = variant.lower()
            if low in seen:
                continue
            seen.add(low)
            out.append(variant)
    return out


def search_tokens(q: str) -> list[str]:
    """Extract meaningful tokens from a natural-language spend question."""
    tokens = re.findall(r"[A-Za-z0-9ÄÖÜäöüß]{2,}", q or "")
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        key = token.lower()
        if key in _STOPWORDS or key in seen:
            continue
        seen.add(key)
        out.append(token)
    return expand_product_tokens(out)


def parse_ask_query(q: str) -> dict[str, object]:
    """Parse NL question into intent + structured filter (merchant/category/tokens)."""
    raw = (q or "").strip()
    ql = raw.lower()
    intent = "visits" if re.search(r"\b(how many|how often|number of|times)\b", ql) else "amount"

    for alias, category in _CATEGORY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", ql):
            return {
                "intent": intent,
                "filter_type": "category",
                "filter_value": category,
                "tokens": [category],
            }

    merchant_match = re.search(
        r"(?:at|to|from)\s+(?:the\s+)?([a-z0-9][\w&.\-äöüß]{1,50})",
        ql,
        re.IGNORECASE,
    )
    if merchant_match:
        entity = merchant_match.group(1).strip()
        if entity.lower() not in _CATEGORY_ALIASES:
            return {
                "intent": intent,
                "filter_type": "merchant",
                "filter_value": entity,
                "tokens": [entity],
            }

    tokens = search_tokens(raw)
    return {
        "intent": intent,
        "filter_type": "tokens" if tokens else "none",
        "filter_value": None,
        "tokens": tokens,
    }


def _clause_from_tokens(tokens: list[str]) -> ColumnElement[bool] | None:
    if not tokens:
        return None
    needles = [f"%{t}%" for t in tokens]
    clauses = []
    for needle in needles:
        clauses.append(
            or_(
                Expense.merchant.ilike(needle),
                Expense.category.ilike(needle),
                Expense.note.ilike(needle),
                Expense.id.in_(
                    select(ExpenseLineItem.expense_id).where(
                        ExpenseLineItem.description.ilike(needle)
                    )
                ),
            )
        )
    return or_(*clauses)


def _ask_filter_clause(parsed: dict[str, object]) -> ColumnElement[bool] | None:
    """Build WHERE clause from parse_ask_query result."""
    filter_type = str(parsed.get("filter_type") or "none")
    if filter_type == "category":
        value = str(parsed.get("filter_value") or "")
        return Expense.category.ilike(f"%{value}%")
    if filter_type == "merchant":
        value = str(parsed.get("filter_value") or "")
        needle = f"%{value}%"
        return or_(
            Expense.merchant.ilike(needle),
            Expense.note.ilike(needle),
        )
    if filter_type == "tokens":
        tokens = parsed.get("tokens")
        if isinstance(tokens, list) and tokens:
            return _clause_from_tokens([str(t) for t in tokens])
    return None


def merchant_breakdown(
    db: Session,
    *,
    settings: Settings,
    limit: int = 15,
) -> list[dict[str, object]]:
    """Top merchants by visit count (posted expenses only)."""
    amount_col = Expense.amount_base if settings.feature_multi_currency else Expense.amount
    stmt = (
        select(
            Expense.merchant,
            func.count(Expense.id),
            func.coalesce(func.sum(amount_col), 0),
        )
        .where(Expense.status == "posted")
        .where(_exclude_active_duplicates())
        .group_by(Expense.merchant)
        .order_by(func.count(Expense.id).desc(), Expense.merchant)
        .limit(max(1, min(limit, 50)))
    )
    rows = db.execute(stmt).all()
    out: list[dict[str, object]] = []
    for merchant, visits, total in rows:
        label = (merchant or "").strip() or "(empty merchant)"
        out.append(
            {
                "merchant": label,
                "visits": int(visits or 0),
                "total": float(
                    Decimal(str(total or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
                ),
            }
        )
    return out


def try_deterministic_answer(aggregate: dict[str, object]) -> str | None:
    """Return a grounded answer without LLM when the aggregate is unambiguous."""
    currency = str(aggregate.get("currency") or "EUR")
    line_matches = aggregate.get("line_matches")
    line_total = aggregate.get("line_total")
    line_count = int(aggregate.get("line_match_count") or 0)
    if isinstance(line_matches, list) and line_count > 0:
        samples = []
        for m in line_matches[:5]:
            if not isinstance(m, dict):
                continue
            samples.append(
                f"{m.get('description')} ({m.get('amount')} {m.get('currency', currency)})"
            )
        extra = f" Examples: {'; '.join(samples)}." if samples else ""
        return (
            f"Found {line_count} matching line item(s) totaling "
            f"{line_total} {currency}.{extra}"
        )

    intent = str(aggregate.get("intent") or "")
    if intent != "visits":
        return None
    parsed = aggregate.get("filter")
    if not isinstance(parsed, dict):
        return None
    count = int(aggregate.get("count") or 0)
    posted = int(aggregate.get("posted_total_count") or 0)
    filter_type = str(parsed.get("filter_type") or "")
    filter_value = parsed.get("filter_value")

    if filter_type == "merchant" and filter_value:
        name = str(filter_value)
        empty = int(aggregate.get("empty_merchant_count") or 0)
        hint = ""
        if count <= 2 and empty > 5:
            hint = (
                f" Note: {empty} expenses have no merchant name — OCR may have missed the store."
            )
        return f"You have {count} posted expense(s) matching “{name}” (of {posted} total).{hint}"

    if filter_type == "category" and filter_value:
        cat = str(filter_value)
        return f"You have {count} posted {cat} expense(s) (of {posted} total)."

    if filter_type in {"tokens", "none"}:
        breakdown = aggregate.get("merchant_breakdown")
        if isinstance(breakdown, list) and breakdown:
            top = breakdown[:5]
            parts = [f"{m['merchant']}: {m['visits']}" for m in top if isinstance(m, dict)]
            return (
                f"You have {posted} posted expenses. "
                f"Top merchants by visits: {', '.join(parts)}."
            )
    return None


def _text_match_clause(q: str) -> ColumnElement[bool] | None:
    """Build OR clause over merchant/category/note for phrase or tokens."""
    parsed = parse_ask_query(q)
    return _ask_filter_clause(parsed)


def replace_line_items(
    db: Session,
    *,
    expense_id: int,
    items: list[dict[str, object]],
    currency: str,
) -> list[ExpenseLineItem]:
    """Replace all line items for an expense (empty list clears)."""
    existing = list(
        db.scalars(
            select(ExpenseLineItem).where(ExpenseLineItem.expense_id == expense_id)
        ).all()
    )
    for row in existing:
        db.delete(row)
    db.flush()

    currency_norm = currency.strip().upper()[:3] or "EUR"
    created: list[ExpenseLineItem] = []
    for idx, raw in enumerate(items):
        desc = str(raw.get("description") or "").strip()
        if not desc:
            continue
        try:
            amount = Decimal(str(raw.get("amount") or "0").replace(",", ".")).quantize(
                _MONEY_QUANT, rounding=ROUND_HALF_UP
            )
        except (InvalidOperation, ValueError):
            amount = Decimal("0.00")
        qty: Decimal | None = None
        if raw.get("quantity") is not None and str(raw.get("quantity")).strip() != "":
            try:
                qty = Decimal(str(raw["quantity"]).replace(",", "."))
            except (InvalidOperation, ValueError):
                qty = None
        row = ExpenseLineItem(
            expense_id=expense_id,
            description=desc[:512],
            quantity=qty,
            amount=amount,
            currency=currency_norm,
            position=idx,
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    from app.services.duplicates import refresh_duplicate_link

    refresh_duplicate_link(db, expense_id=expense_id)
    return created


def list_line_items(db: Session, *, expense_id: int) -> list[ExpenseLineItem]:
    return list(
        db.scalars(
            select(ExpenseLineItem)
            .where(ExpenseLineItem.expense_id == expense_id)
            .order_by(ExpenseLineItem.position, ExpenseLineItem.id)
        ).all()
    )


def query_line_matches(
    db: Session,
    *,
    q: str | None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, object]]:
    """Return posted line items matching q tokens (for Ask grounding)."""
    if not (q or "").strip():
        return []
    tokens = search_tokens(q or "")
    if not tokens:
        return []
    stmt = (
        select(ExpenseLineItem, Expense)
        .join(Expense, Expense.id == ExpenseLineItem.expense_id)
        .where(Expense.status == "posted")
        .where(_exclude_active_duplicates())
    )
    if start:
        stmt = stmt.where(Expense.spent_on >= start)
    if end:
        stmt = stmt.where(Expense.spent_on <= end)
    desc_clauses = [ExpenseLineItem.description.ilike(f"%{t}%") for t in tokens]
    stmt = stmt.where(or_(*desc_clauses)).order_by(Expense.spent_on.desc()).limit(50)
    rows = db.execute(stmt).all()
    out: list[dict[str, object]] = []
    for item, exp in rows:
        out.append(
            {
                "expense_id": exp.id,
                "spent_on": exp.spent_on.isoformat(),
                "merchant": exp.merchant,
                "description": item.description,
                "amount": float(
                    Decimal(str(item.amount)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
                ),
                "currency": item.currency,
            }
        )
    return out


def add_expense(
    db: Session,
    *,
    settings: Settings,
    spent_on: date,
    amount: Decimal,
    currency: str,
    merchant: str = "",
    category: str = "",
    note: str = "",
    source: str = "manual",
    status: str = "posted",
    receipt_path: str | None = None,
    bank_ref: str | None = None,
    fx_rate_override: Decimal | None = None,
) -> Expense:
    """Persist an expense; convert to base currency when FEATURE_MULTI_CURRENCY."""
    from app.services.fx import to_base_amount

    amount = amount.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    currency_norm = currency.strip().upper()
    base = settings.base_currency.upper()
    amount_base, _rate, fx_err = to_base_amount(
        settings,
        amount=amount,
        currency=currency_norm,
        spent_on=spent_on,
        fx_rate_override=fx_rate_override,
    )
    base_currency: str | None = base if settings.feature_multi_currency else currency_norm
    if not settings.feature_multi_currency:
        amount_base = amount
        base_currency = currency_norm
    elif fx_err:
        logger.info(
            "Stored foreign currency without FX conversion: %s",
            fx_err,
            extra={"currency": currency_norm, "base": base},
        )

    row = Expense(
        spent_on=spent_on,
        amount=amount,
        currency=currency_norm,
        amount_base=amount_base,
        base_currency=base_currency,
        merchant=merchant.strip(),
        category=category.strip(),
        note=note.strip(),
        source=source,
        status=status,
        receipt_path=receipt_path,
        bank_ref=bank_ref,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if status in {"pending", "posted"}:
        from app.services.duplicates import refresh_duplicate_link

        refresh_duplicate_link(db, expense_id=row.id)
        db.refresh(row)
    return row


def update_expense(
    db: Session,
    *,
    settings: Settings,
    expense_id: int,
    spent_on: date,
    amount: Decimal,
    currency: str,
    merchant: str = "",
    category: str = "",
    note: str = "",
    status: str | None = None,
    fx_rate_override: Decimal | None = None,
) -> Expense | None:
    """Update fields on an expense; refresh base amount via FX when needed."""
    from app.services.fx import to_base_amount

    row = db.get(Expense, expense_id)
    if row is None:
        return None
    amount = amount.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    currency_norm = currency.strip().upper()
    row.spent_on = spent_on
    row.amount = amount
    row.currency = currency_norm
    row.merchant = merchant.strip()
    row.category = category.strip()
    row.note = note.strip()
    if status is not None:
        row.status = status

    if settings.feature_multi_currency:
        amount_base, _rate, _err = to_base_amount(
            settings,
            amount=amount,
            currency=currency_norm,
            spent_on=spent_on,
            fx_rate_override=fx_rate_override,
        )
        row.amount_base = amount_base
        row.base_currency = settings.base_currency.upper()
    else:
        row.amount_base = amount
        row.base_currency = currency_norm

    db.commit()
    db.refresh(row)
    if row.status in {"pending", "posted"}:
        from app.services.duplicates import refresh_duplicate_link

        refresh_duplicate_link(db, expense_id=row.id)
        db.refresh(row)
    return row


def delete_expense(db: Session, *, expense_id: int) -> bool:
    """Delete an expense by id. Returns True if a row was removed."""
    row = db.get(Expense, expense_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def _exclude_active_duplicates() -> ColumnElement[bool]:
    """Ask/totals: keep originals and dismissed suspects; drop active duplicates."""
    return or_(
        Expense.duplicate_of_id.is_(None),
        Expense.duplicate_dismissed.is_(True),
    )


def list_expenses(
    db: Session,
    *,
    limit: int = 50,
    category: str | None = None,
    merchant: str | None = None,
    q: str | None = None,
    status: str | None = "posted",
    start: date | None = None,
    end: date | None = None,
) -> list[Expense]:
    """Return recent expenses with optional filters (default: posted only)."""
    stmt: Select[tuple[Expense]] = select(Expense).order_by(
        Expense.spent_on.desc(), Expense.id.desc()
    )
    if status is not None:
        stmt = stmt.where(Expense.status == status)
    if category:
        cat = category.strip()
        if cat.lower() == "uncategorized":
            stmt = stmt.where(or_(Expense.category == "", Expense.category.is_(None)))
        else:
            stmt = stmt.where(Expense.category.ilike(cat))
    if merchant:
        merch = merchant.strip()
        if merch.lower() == "unknown merchant":
            stmt = stmt.where(or_(Expense.merchant == "", Expense.merchant.is_(None)))
        else:
            stmt = stmt.where(Expense.merchant.ilike(f"%{merch}%"))
    if start is not None:
        stmt = stmt.where(Expense.spent_on >= start)
    if end is not None:
        stmt = stmt.where(Expense.spent_on <= end)
    text_clause = _text_match_clause(q) if q else None
    if text_clause is not None:
        stmt = stmt.where(text_clause)
    stmt = stmt.limit(max(1, min(limit, 200)))
    return list(db.scalars(stmt).all())


def list_pending(db: Session, *, limit: int = 50) -> list[Expense]:
    """Return pending receipt drafts newest first (OCR complete, awaiting confirm)."""
    return list_expenses(db, limit=limit, status="pending")


def list_processing(db: Session, *, limit: int = 100) -> list[Expense]:
    """Return receipts still in the OCR spool (not yet in Pending)."""
    return list_expenses(db, limit=limit, status="processing")


def count_expenses(db: Session, *, status: str) -> int:
    """Count expenses with a given status."""
    stmt = select(func.count(Expense.id)).where(Expense.status == status)
    return int(db.scalar(stmt) or 0)


def count_empty_merchants(db: Session, *, status: str = "posted") -> int:
    """Posted expenses with blank merchant (OCR gap indicator)."""
    return int(
        db.scalar(
            select(func.count(Expense.id)).where(
                Expense.status == status,
                or_(Expense.merchant == "", Expense.merchant.is_(None)),
                _exclude_active_duplicates(),
            )
        )
        or 0
    )


def query_spend(
    db: Session,
    *,
    settings: Settings,
    start: date | None = None,
    end: date | None = None,
    q: str | None = None,
) -> dict[str, object]:
    """Sum spend for a window / text filter — MCP and Q&A use this."""
    amount_col = Expense.amount_base if settings.feature_multi_currency else Expense.amount
    currency_label = (
        settings.base_currency.upper() if settings.feature_multi_currency else "mixed"
    )
    parsed = parse_ask_query(q or "") if q else None

    base_stmt = select(func.coalesce(func.sum(amount_col), 0), func.count(Expense.id)).where(
        Expense.status == "posted",
        _exclude_active_duplicates(),
    )
    if start:
        base_stmt = base_stmt.where(Expense.spent_on >= start)
    if end:
        base_stmt = base_stmt.where(Expense.spent_on <= end)
    posted_total, posted_total_count = db.execute(base_stmt).one()

    stmt = base_stmt
    text_clause = _ask_filter_clause(parsed) if parsed else None
    if text_clause is not None:
        stmt = stmt.where(text_clause)
    total, count = db.execute(stmt).one()

    empty_merchant_count = count_empty_merchants(db)

    line_matches: list[dict[str, object]] = []
    line_total = 0.0
    if q and settings.feature_line_items:
        line_matches = query_line_matches(db, q=q, start=start, end=end)
        line_total = float(
            sum(
                (
                    Decimal(str(m["amount"])).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
                    for m in line_matches
                ),
                Decimal("0.00"),
            )
        )
    return {
        "total": float(
            Decimal(str(total or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        ),
        "currency": currency_label,
        "count": int(count or 0),
        "posted_total_count": int(posted_total_count or 0),
        "posted_total": float(
            Decimal(str(posted_total or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        ),
        "empty_merchant_count": empty_merchant_count,
        "intent": parsed.get("intent") if parsed else None,
        "filter": parsed,
        "merchant_breakdown": merchant_breakdown(db, settings=settings),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "q": q,
        "tokens": parsed.get("tokens", []) if parsed else [],
        "line_matches": line_matches,
        "line_total": line_total,
        "line_match_count": len(line_matches),
    }
