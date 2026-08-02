"""Expense domain services — shared by HTTP and MCP."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Expense, ExpenseLineItem

logger = logging.getLogger("xtav2.expenses")

_MONEY_QUANT = Decimal("0.01")
_STOPWORDS = frozenset(
    {
        "how",
        "much",
        "did",
        "i",
        "am",
        "is",
        "are",
        "spend",
        "spent",
        "spending",
        "paying",
        "pay",
        "cost",
        "costs",
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
        "average",
        "avg",
        "mean",
        "per",
        "each",
        "monthly",
        "yearly",
        "daily",
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
        # top-N ranking noise
        "top",
        "most",
        "expensive",
        "highest",
        "biggest",
        "largest",
        "items",
        "item",
        "purchases",
        "expenses",
        "transactions",
        "list",
        "show",
        "give",
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


def _is_product_term(word: str) -> bool:
    """True when word is a known product Ask synonym (chocolate, kebab, …)."""
    key = word.casefold()
    if key in _PRODUCT_SYNONYMS:
        return True
    return any(key == syn.casefold() for syns in _PRODUCT_SYNONYMS.values() for syn in syns)


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


def period_bounds_for_query(q: str, *, today: date | None = None) -> tuple[date | None, date | None]:
    """Map phrases like 'this month' / 'in 2025' to inclusive [start, end] dates."""
    ql = (q or "").lower()
    day = today or datetime.now(ZoneInfo(get_settings().app_timezone)).date()

    year_match = re.search(r"\b(?:in|for|during)\s+(20\d{2})\b", ql) or re.search(
        r"\b(20\d{2})\b", ql
    )
    if year_match:
        year = int(year_match.group(1))
        return date(year, 1, 1), date(year, 12, 31)

    if re.search(r"\b(this month|mtd|current month)\b", ql):
        return day.replace(day=1), day
    if re.search(r"\blast month\b", ql):
        first = day.replace(day=1)
        last_end = first - timedelta(days=1)
        return last_end.replace(day=1), last_end
    if re.search(r"\b(this year|ytd)\b", ql):
        return date(day.year, 1, 1), day
    if re.search(r"\b(this week)\b", ql):
        start = day - timedelta(days=day.weekday())
        return start, day
    return None, None


def _entity_after_preposition(ql: str) -> str | None:
    """Extract merchant/product entity after at/on/to/from (may be multi-word)."""
    match = re.search(
        r"\b(?:at|to|from|on)\s+(?:the\s+)?(.+)$",
        ql,
        re.IGNORECASE,
    )
    if not match:
        return None
    rest = re.split(r"[?!.]", match.group(1), maxsplit=1)[0].strip()
    words = re.findall(r"[a-z0-9][\w&.\-äöüß]*", rest, flags=re.IGNORECASE)
    trail_stop = _STOPWORDS | {
        "during",
        "between",
        "since",
        "until",
        "before",
        "after",
        "today",
        "yesterday",
        "next",
    }
    taken: list[str] = []
    for word in words:
        lower = word.lower()
        if re.fullmatch(r"20\d{2}", lower):
            break
        if lower in trail_stop:
            break
        taken.append(word)
        if len(taken) >= 4:
            break
    if not taken:
        return None
    entity = " ".join(taken).strip()
    if not entity or entity.lower() in _STOPWORDS:
        return None
    return entity


def parse_ask_query(q: str) -> dict[str, object]:
    """Parse NL question into intent + structured filter (merchant/category/tokens)."""
    raw = (q or "").strip()
    ql = raw.lower()

    top_n = 5
    top_match = re.search(r"\btop\s+(\d{1,2})\b", ql)
    if top_match:
        top_n = max(1, min(int(top_match.group(1)), 20))

    if re.search(
        r"\b(most expensive|highest|biggest|largest|top\s+\d+)\b",
        ql,
    ) or (re.search(r"\btop\b", ql) and re.search(r"\b(item|items|purchase|expense)", ql)):
        intent = "top_expensive"
        wants_items = bool(
            re.search(r"\b(item|items|product|products|line|sku)\b", ql)
        ) or not re.search(r"\b(expense|expenses|transaction|purchase|purchases)\b", ql)
        # Default "most expensive items" → line items; "expenses" → headers.
        if re.search(r"\b(expense|expenses|transaction|transactions)\b", ql) and not re.search(
            r"\b(item|items|product)\b", ql
        ):
            wants_items = False
        return {
            "intent": intent,
            "filter_type": "none",
            "filter_value": None,
            "tokens": [],
            "top_n": top_n,
            "wants_items": wants_items,
        }

    intent = "visits" if re.search(r"\b(how many|how often|number of|times)\b", ql) else "amount"
    if re.search(r"\b(average|avg|mean)\b", ql) and re.search(
        r"\b(month|monthly|week|weekly|day|daily|year|yearly)\b", ql
    ):
        return {
            "intent": "average",
            "filter_type": "none",
            "filter_value": None,
            "tokens": [],
            "top_n": top_n,
            "wants_items": False,
        }

    for alias, category in _CATEGORY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", ql):
            return {
                "intent": intent,
                "filter_type": "category",
                "filter_value": category,
                "tokens": [category],
                "top_n": top_n,
                "wants_items": False,
            }

    entity = _entity_after_preposition(ql)
    if entity:
        el = entity.lower()
        if el not in _STOPWORDS and el not in _CATEGORY_ALIASES:
            # "on Schokolade/kebab" is a product Ask, not a merchant name.
            if _is_product_term(entity.split()[0] if entity else entity):
                product_tokens = expand_product_tokens([entity.split()[0]])
                return {
                    "intent": intent,
                    "filter_type": "tokens",
                    "filter_value": None,
                    "tokens": product_tokens,
                    "top_n": top_n,
                    "wants_items": False,
                }
            return {
                "intent": intent,
                "filter_type": "merchant",
                "filter_value": entity,
                "tokens": [entity],
                "top_n": top_n,
                "wants_items": False,
            }

    tokens = search_tokens(raw)
    return {
        "intent": intent,
        "filter_type": "tokens" if tokens else "none",
        "filter_value": None,
        "tokens": tokens,
        "top_n": top_n,
        "wants_items": False,
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
    start: date | None = None,
    end: date | None = None,
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
        .where(_exclude_non_spend())
        .group_by(Expense.merchant)
        .order_by(func.count(Expense.id).desc(), Expense.merchant)
        .limit(max(1, min(limit, 50)))
    )
    if start:
        stmt = stmt.where(Expense.spent_on >= start)
    if end:
        stmt = stmt.where(Expense.spent_on <= end)
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


def top_expensive_line_items(
    db: Session,
    *,
    limit: int = 5,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, object]]:
    """Highest-priced receipt line items in a window (posted, non-duplicate)."""
    stmt = (
        select(ExpenseLineItem, Expense)
        .join(Expense, Expense.id == ExpenseLineItem.expense_id)
        .where(Expense.status == "posted")
        .where(_exclude_active_duplicates())
        .where(_exclude_non_spend())
        .order_by(ExpenseLineItem.amount.desc(), ExpenseLineItem.id.desc())
        .limit(max(1, min(limit, 50)))
    )
    if start:
        stmt = stmt.where(Expense.spent_on >= start)
    if end:
        stmt = stmt.where(Expense.spent_on <= end)
    rows = db.execute(stmt).all()
    out: list[dict[str, object]] = []
    for item, exp in rows:
        out.append(
            {
                "kind": "line_item",
                "description": item.description,
                "amount": float(
                    Decimal(str(item.amount)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
                ),
                "currency": item.currency,
                "spent_on": exp.spent_on.isoformat(),
                "merchant": exp.merchant,
                "expense_id": exp.id,
            }
        )
    return out


def top_expensive_expenses(
    db: Session,
    *,
    settings: Settings,
    limit: int = 5,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, object]]:
    """Highest posted expense totals in a window."""
    amount_col = Expense.amount_base if settings.feature_multi_currency else Expense.amount
    currency_label = (
        settings.base_currency.upper() if settings.feature_multi_currency else None
    )
    stmt = (
        select(Expense)
        .where(Expense.status == "posted")
        .where(_exclude_active_duplicates())
        .where(_exclude_non_spend())
        .order_by(amount_col.desc(), Expense.id.desc())
        .limit(max(1, min(limit, 50)))
    )
    if start:
        stmt = stmt.where(Expense.spent_on >= start)
    if end:
        stmt = stmt.where(Expense.spent_on <= end)
    rows = list(db.scalars(stmt).all())
    out: list[dict[str, object]] = []
    for exp in rows:
        amt = exp.amount_base if settings.feature_multi_currency else exp.amount
        out.append(
            {
                "kind": "expense",
                "description": (exp.merchant or exp.category or "Expense").strip(),
                "amount": float(
                    Decimal(str(amt or 0)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
                ),
                "currency": currency_label or exp.currency,
                "spent_on": exp.spent_on.isoformat(),
                "merchant": exp.merchant,
                "expense_id": exp.id,
            }
        )
    return out


def try_deterministic_answer(aggregate: dict[str, object]) -> str | None:
    """Return a grounded answer without LLM when the aggregate is unambiguous."""
    currency = str(aggregate.get("currency") or "EUR")
    intent = str(aggregate.get("intent") or "")

    if intent == "top_expensive":
        rows = aggregate.get("top_expensive")
        if not isinstance(rows, list) or not rows:
            window = aggregate.get("period_label") or "that period"
            return f"No expensive items found for {window}."
        n = len(rows)
        parts: list[str] = []
        for i, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            label = str(row.get("description") or row.get("merchant") or "item")
            amt = format_money(Decimal(str(row.get("amount") or 0)))
            ccy = str(row.get("currency") or currency)
            merch = str(row.get("merchant") or "").strip()
            when = str(row.get("spent_on") or "")
            tail = f" · {merch}" if merch and merch.lower() not in label.lower() else ""
            parts.append(f"{i}. {label}: {amt} {ccy}{tail} ({when})")
        kind = "line items" if rows and rows[0].get("kind") == "line_item" else "expenses"
        return f"Top {n} most expensive {kind}: " + "; ".join(parts) + "."

    if intent == "average":
        return (
            "I can’t compute average spend per month yet. "
            "Try Insights for MoM totals, or ask “How much did I spend this month?”"
        )

    line_matches = aggregate.get("line_matches")
    line_total = aggregate.get("line_total")
    line_count = int(aggregate.get("line_match_count") or 0)
    parsed_early = aggregate.get("filter")
    filter_type_early = (
        str(parsed_early.get("filter_type") or "") if isinstance(parsed_early, dict) else ""
    )
    # Prefer line totals when: product Ask, or merchant/name Ask that matched
    # no expense headers (renamed SKU on a receipt — e.g. "on Kevin" at EDEKA).
    prefer_lines = (
        isinstance(line_matches, list)
        and line_count > 0
        and filter_type_early != "category"
        and (
            int(aggregate.get("count") or 0) == 0
            or (
                filter_type_early not in {"merchant", "category"}
                and _tokens_look_like_product(
                    parsed_early if isinstance(parsed_early, dict) else {}
                )
            )
        )
    )
    if prefer_lines and isinstance(line_matches, list):
        entity = ""
        if isinstance(parsed_early, dict):
            entity = str(
                parsed_early.get("filter_value")
                or (
                    " ".join(str(t) for t in parsed_early.get("tokens") or [])
                    if isinstance(parsed_early.get("tokens"), list)
                    else ""
                )
                or ""
            ).strip()
        options = _line_disambiguation_options(line_matches)
        if len(options) >= 2:
            aggregate["clarify_options"] = options
            labels = ", ".join(f"“{o['label']}”" for o in options[:4])
            return (
                f"I found multiple matches for “{entity or 'that'}” "
                f"({labels}). Choose one below — I need something more specific."
            )
    if prefer_lines:
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
            f"{format_money(Decimal(str(line_total or 0)))} {currency}.{extra}"
        )

    if intent == "amount":
        parsed = parsed_early if isinstance(parsed_early, dict) else None
        total = format_money(Decimal(str(aggregate.get("total") or 0)))
        count = int(aggregate.get("count") or 0)
        if parsed and str(parsed.get("filter_type") or "") == "merchant":
            name = str(parsed.get("filter_value") or "that merchant")
            return f"You spent {total} {currency} on “{name}” across {count} expense(s)."
        if parsed and str(parsed.get("filter_type") or "") == "category":
            cat = str(parsed.get("filter_value") or "that category")
            return f"You spent {total} {currency} on {cat} across {count} expense(s)."
        if parsed and str(parsed.get("filter_type") or "") == "tokens":
            tokens = parsed.get("tokens") or []
            label = " ".join(str(t) for t in tokens) if isinstance(tokens, list) else "that"
            return f"You spent {total} {currency} matching “{label}” across {count} expense(s)."
        return f"You spent {total} {currency} across {count} expense(s)."

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


def _tokens_look_like_product(parsed: dict[str, object]) -> bool:
    """True when Ask tokens map to product synonyms (kebab, milk, …)."""
    tokens = parsed.get("tokens")
    if not isinstance(tokens, list):
        return False
    for token in tokens:
        key = str(token).casefold()
        if key in _PRODUCT_SYNONYMS:
            return True
    return False


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


def _word_boundary_match(haystack: str, needle: str) -> bool:
    """True when needle appears as a whole word/phrase (case-insensitive)."""
    text = (haystack or "").strip()
    token = (needle or "").strip()
    if not text or not token:
        return False
    return bool(re.search(rf"(?i)\b{re.escape(token)}\b", text))


def _refine_text_matches(
    rows: list[dict[str, object]],
    *,
    tokens: list[str],
    field: str = "description",
) -> list[dict[str, object]]:
    """Prefer word-boundary hits; fall back to substring rows only if none."""
    if not rows or not tokens:
        return rows
    strict = [
        row
        for row in rows
        if any(_word_boundary_match(str(row.get(field) or ""), t) for t in tokens)
    ]
    return strict if strict else rows


def _line_disambiguation_options(
    line_matches: list[dict[str, object]],
) -> list[dict[str, object]]:
    """When multiple distinct descriptions match, offer pick-one options."""
    groups: dict[str, dict[str, object]] = {}
    for match in line_matches:
        label = str(match.get("description") or "").strip()
        key = label.casefold()
        if not key:
            continue
        group = groups.get(key)
        if group is None:
            group = {"label": label, "total": Decimal("0.00"), "count": 0}
            groups[key] = group
        group["total"] = (
            Decimal(str(group["total"])) + Decimal(str(match.get("amount") or 0))
        ).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        group["count"] = int(group["count"]) + 1
    if len(groups) < 2:
        return []
    ranked = sorted(
        groups.values(),
        key=lambda g: (Decimal(str(g["total"])), int(g["count"])),
        reverse=True,
    )[:6]
    out: list[dict[str, object]] = []
    for group in ranked:
        label = str(group["label"])
        out.append(
            {
                "label": label,
                "count": int(group["count"]),
                "total": float(Decimal(str(group["total"]))),
                "q": f"How much on {label}",
                "button": label,
            }
        )
    return out


def query_line_matches(
    db: Session,
    *,
    q: str | None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, object]]:
    """Return posted line items matching product tokens or merchant-entity text.

    Category Asks stay header-only. Merchant Asks also search line descriptions so
    renamed SKUs (not store names) still resolve when header merchant misses.
    Prefers whole-word matches so ``tom`` does not match ``RISPENTOMATE``.
    """
    if not (q or "").strip():
        return []
    parsed = parse_ask_query(q or "")
    filter_type = str(parsed.get("filter_type") or "none")
    if filter_type == "category":
        return []

    tokens: list[str] = []
    if filter_type == "merchant":
        value = str(parsed.get("filter_value") or "").strip()
        if value:
            tokens = [value]
    else:
        tokens_raw = parsed.get("tokens")
        tokens = [str(t) for t in tokens_raw] if isinstance(tokens_raw, list) else []
        if not tokens:
            return []
        # Only search line items for product-style queries (synonyms) or lone tokens
        # that are not already treated as merchants above.
        if not _tokens_look_like_product(parsed) and len(tokens) > 1:
            return []

    if not tokens:
        return []
    stmt = (
        select(ExpenseLineItem, Expense)
        .join(Expense, Expense.id == ExpenseLineItem.expense_id)
        .where(Expense.status == "posted")
        .where(_exclude_active_duplicates())
        .where(_exclude_non_spend())
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
    return _refine_text_matches(out, tokens=tokens, field="description")


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


def _exclude_non_spend() -> ColumnElement[bool]:
    """Ask/Insights: drop family/savings transfers (still listed on Expenses)."""
    from app.services.transfers import exclude_non_spend

    return exclude_non_spend()



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
                _exclude_non_spend(),
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

    # Apply NL period ("this month") when caller did not pass explicit bounds.
    period_label = None
    if q and start is None and end is None:
        p_start, p_end = period_bounds_for_query(q)
        start, end = p_start, p_end
        if start and end:
            period_label = f"{start.isoformat()} → {end.isoformat()}"

    base_stmt = select(func.coalesce(func.sum(amount_col), 0), func.count(Expense.id)).where(
        Expense.status == "posted",
        _exclude_active_duplicates(),
        _exclude_non_spend(),
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

    intent = str(parsed.get("intent") if parsed else "") or None
    top_expensive: list[dict[str, object]] = []
    if parsed and intent == "top_expensive":
        top_n = int(parsed.get("top_n") or 5)
        wants_items = bool(parsed.get("wants_items"))
        if wants_items and settings.feature_line_items:
            top_expensive = top_expensive_line_items(
                db, limit=top_n, start=start, end=end
            )
        if not top_expensive:
            top_expensive = top_expensive_expenses(
                db, settings=settings, limit=top_n, start=start, end=end
            )

    line_matches: list[dict[str, object]] = []
    line_total = 0.0
    if q and settings.feature_line_items and intent != "top_expensive":
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
        "intent": intent,
        "filter": parsed,
        "merchant_breakdown": merchant_breakdown(
            db, settings=settings, start=start, end=end
        ),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "period_label": period_label,
        "q": q,
        "tokens": parsed.get("tokens", []) if parsed else [],
        "line_matches": line_matches,
        "line_total": line_total,
        "line_match_count": len(line_matches),
        "top_expensive": top_expensive,
    }
