"""FX conversion for multi-currency ledger (base = BASE_CURRENCY)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache

import httpx

from app.config import Settings

logger = logging.getLogger("xtav2.fx")

_MONEY = Decimal("0.01")
_RATE_QUANT = Decimal("0.000001")

# Common ISO codes for UI select (ECB set + frequent travel).
COMMON_CURRENCIES: tuple[str, ...] = (
    "EUR",
    "USD",
    "GBP",
    "CHF",
    "SEK",
    "NOK",
    "DKK",
    "PLN",
    "CZK",
    "JPY",
    "CAD",
    "AUD",
    "INR",
)


def _frankfurter_base(settings: Settings) -> str:
    return (settings.fx_api_base_url or "https://api.frankfurter.app").rstrip("/")


def convert_amount(
    amount: Decimal,
    *,
    rate: Decimal,
) -> Decimal:
    return (amount * rate).quantize(_MONEY, rounding=ROUND_HALF_UP)


@lru_cache(maxsize=256)
def _fetch_rate_cached(api_base: str, on_iso: str, source: str, target: str) -> str:
    """Return rate as string for lru_cache; raises on failure."""
    url = f"{api_base}/{on_iso}"
    params = {"from": source, "to": target}
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, params=params)
        if response.status_code == 404:
            # Weekend/holiday — walk back up to 7 days (ECB publishes working days).
            on = date.fromisoformat(on_iso)
            for days in range(1, 8):
                prev = (on - timedelta(days=days)).isoformat()
                retry = client.get(f"{api_base}/{prev}", params=params)
                if retry.status_code == 200:
                    response = retry
                    break
            else:
                response.raise_for_status()
        else:
            response.raise_for_status()
        data = response.json()
    rates = data.get("rates") or {}
    if target not in rates:
        raise RuntimeError(f"No FX rate {source}→{target} for {on_iso}")
    return str(rates[target])


def get_fx_rate(
    settings: Settings,
    *,
    source: str,
    target: str,
    on: date,
    override: Decimal | None = None,
) -> Decimal:
    """Rate such that amount_target = amount_source * rate."""
    src = source.strip().upper()
    tgt = target.strip().upper()
    if override is not None and override > 0:
        return override.quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)
    if src == tgt:
        return Decimal(1)
    raw = _fetch_rate_cached(_frankfurter_base(settings), on.isoformat(), src, tgt)
    return Decimal(raw).quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)


def to_base_amount(
    settings: Settings,
    *,
    amount: Decimal,
    currency: str,
    spent_on: date,
    fx_rate_override: Decimal | None = None,
) -> tuple[Decimal | None, Decimal | None, str | None]:
    """
    Convert to BASE_CURRENCY.
    Returns (amount_base, rate_used, error_message).
    """
    amount = amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
    currency_norm = currency.strip().upper()
    base = settings.base_currency.strip().upper()
    if not settings.feature_multi_currency:
        return amount, Decimal(1), None
    if currency_norm == base:
        return amount, Decimal(1), None
    try:
        rate = get_fx_rate(
            settings,
            source=currency_norm,
            target=base,
            on=spent_on,
            override=fx_rate_override,
        )
        return convert_amount(amount, rate=rate), rate, None
    except (httpx.HTTPError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        logger.warning(
            "FX conversion failed %s→%s on %s: %s",
            currency_norm,
            base,
            spent_on,
            exc,
        )
        return None, None, str(exc)


def fx_health(settings: Settings) -> dict[str, object]:
    """Probe Frankfurter with a known pair (Production-Path Parity)."""
    base = settings.base_currency.strip().upper() or "EUR"
    other = "USD" if base != "USD" else "EUR"
    try:
        rate = get_fx_rate(
            settings,
            source=other,
            target=base,
            on=datetime.now(UTC).date() - timedelta(days=1),
        )
        return {
            "status": "ok",
            "api": _frankfurter_base(settings),
            "sample": f"1 {other} = {rate} {base}",
            "reachable": True,
        }
    except (httpx.HTTPError, RuntimeError, ValueError, TypeError) as exc:
        return {
            "status": "error",
            "api": _frankfurter_base(settings),
            "detail": str(exc),
            "reachable": False,
        }
