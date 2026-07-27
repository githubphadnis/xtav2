"""Tool-calling Ask agent — Ollama picks spend tools; Postgres stays truth."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations.ollama import chat_ollama, parse_tool_calls
from app.services import expenses as expense_service

logger = logging.getLogger("xtav2.ask_agent")

_ASK_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_spend",
            "description": (
                "Query posted expenses and matching receipt line items. "
                "Use for totals, visit counts, merchants, and products "
                "(e.g. kebab, Schokolade). Pass the user's focus as q."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Search phrase, merchant, or product name",
                    }
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "merchant_breakdown",
            "description": "List top merchants by visit count and spend.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

_SYSTEM = (
    "You are xtav2, a concise expense assistant. "
    "Use tools to fetch data from the ledger. "
    "Never invent amounts or visit counts. "
    "For products (kebab, chocolate, milk), call query_spend with that word — "
    "synonyms like Döner are handled in the database. "
    "Answer in short sentences with numbers from tool results."
)


def _run_tool(
    db: Session,
    settings: Settings,
    *,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if name == "query_spend":
        q = str(arguments.get("q") or "").strip()
        return expense_service.query_spend(db, settings=settings, q=q or None)
    if name == "merchant_breakdown":
        return {
            "merchants": expense_service.merchant_breakdown(db, settings=settings),
        }
    return {"error": f"Unknown tool: {name}"}


async def answer_question(
    db: Session,
    settings: Settings,
    *,
    question: str,
    max_rounds: int = 3,
) -> tuple[str, dict[str, object]]:
    """
    Grounded Ask: deterministic first, then Ollama tool loop, then plain aggregate.
    Returns (answer_text, last_aggregate_for_debug).
    """
    aggregate = expense_service.query_spend(db, settings=settings, q=question)
    deterministic = expense_service.try_deterministic_answer(aggregate)
    if deterministic:
        return deterministic, aggregate

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": question},
    ]

    try:
        for _ in range(max_rounds):
            message = await chat_ollama(settings, messages=messages, tools=_ASK_TOOLS)
            tool_calls = parse_tool_calls(message)
            if not tool_calls:
                content = str(message.get("content") or "").strip()
                if content:
                    return content, aggregate
                break

            messages.append(message)
            for call in tool_calls:
                result = _run_tool(
                    db,
                    settings,
                    name=str(call["name"]),
                    arguments=call["arguments"],  # type: ignore[arg-type]
                )
                if call["name"] == "query_spend":
                    aggregate = result
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": call["name"],
                        "content": json.dumps(result, default=str),
                    }
                )

        # Final pass without tools to force a natural-language answer.
        messages.append(
            {
                "role": "user",
                "content": "Answer the original question using only the tool results above.",
            }
        )
        final = await chat_ollama(settings, messages=messages, tools=None)
        content = str(final.get("content") or "").strip()
        if content:
            return content, aggregate
    except Exception:
        logger.exception("Ask tool loop failed; falling back to aggregate prompt")

    # Fallback: one-shot rephrase of the initial aggregate.
    from app.integrations.ollama import ask_ollama

    system = (
        "You are xtav2. Answer ONLY from the aggregate JSON. "
        "Prefer line_matches/line_total for products. Never invent numbers."
    )
    prompt = f"User question: {question}\nAggregate JSON: {aggregate}\nAnswer:"
    try:
        text = await ask_ollama(settings, prompt, system)
        return text, aggregate
    except Exception as exc:
        logger.exception("Ask fallback failed")
        return f"Could not reach Ollama ({exc}). Aggregate: {aggregate}", aggregate
