"""Flexible CSV parsing for bank statement imports (stdlib only)."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_DATE_HEADERS = {
    "date",
    "datum",
    "buchungstag",
    "valuta",
    "wertstellung",
    "booking date",
    "booked",
    "transaction date",
}
_AMOUNT_HEADERS = {
    "amount",
    "betrag",
    "umsatz",
    "value",
    "debit",
    "soll",
}
_MERCHANT_HEADERS = {
    "merchant",
    "vendor",
    "name",
    "payee",
    "verwendungszweck",
    "buchungstext",
    "empfänger",
    "empfaenger",
    "gegenkonto",
    "beschreibung",
    "description",
}
_CURRENCY_HEADERS = {"currency", "waehrung", "währung", "ccy"}
_REF_HEADERS = {
    "reference",
    "referenz",
    "buchungsreferenz",
    "id",
    "transaction id",
    "auftragskonto",
}


@dataclass(frozen=True)
class BankRow:
    """One normalized bank transaction (spend as positive amount)."""

    spent_on: date
    amount: Decimal
    currency: str
    merchant: str
    note: str
    bank_ref: str


def _norm_header(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip().lower())


def _pick_column(headers: list[str], candidates: set[str]) -> str | None:
    for h in headers:
        if _norm_header(h) in candidates:
            return h
    for h in headers:
        n = _norm_header(h)
        for c in candidates:
            if c in n:
                return h
    return None


def _parse_date(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10] if len(text) >= 8 else text, fmt).date()
        except ValueError:
            continue
    # Try ISO with time
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_amount(raw: str) -> Decimal | None:
    text = (raw or "").strip()
    if not text:
        return None
    # European: 1.234,56 or -19,32 ; US: 1,234.56
    neg = text.startswith("-") or text.startswith("(")
    text = text.replace("(", "").replace(")", "").replace("+", "").strip()
    text = text.replace("€", "").replace("EUR", "").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if neg and value > 0:
        value = -value
    return value


def _decode_csv(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _stable_ref(*, spent_on: date, amount: Decimal, merchant: str, row_idx: int) -> str:
    raw = f"{spent_on.isoformat()}|{amount:.2f}|{merchant}|{row_idx}"
    return "csv:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def parse_bank_csv(
    data: bytes,
    *,
    default_currency: str = "EUR",
    filename: str = "statement.csv",
) -> list[BankRow]:
    """Parse a bank CSV into spend rows.

    Debits (negative or expense column) become positive amounts. Credits are skipped.
    """
    text = _decode_csv(data)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
        if sample.count(";") > sample.count(","):
            dialect.delimiter = ";"

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")

    headers = [h for h in reader.fieldnames if h is not None]
    date_col = _pick_column(headers, _DATE_HEADERS)
    amount_col = _pick_column(headers, _AMOUNT_HEADERS)
    merchant_col = _pick_column(headers, _MERCHANT_HEADERS)
    currency_col = _pick_column(headers, _CURRENCY_HEADERS)
    ref_col = _pick_column(headers, _REF_HEADERS)
    if date_col is None or amount_col is None:
        raise ValueError(
            "CSV needs date and amount columns "
            "(e.g. Buchungstag/Datum + Betrag/Amount)"
        )

    parsed: list[tuple[int, date, Decimal, str, str, str]] = []
    for idx, raw in enumerate(reader):
        spent = _parse_date(str(raw.get(date_col) or ""))
        amount = _parse_amount(str(raw.get(amount_col) or ""))
        if spent is None or amount is None or amount == 0:
            continue
        merchant = ""
        if merchant_col:
            merchant = str(raw.get(merchant_col) or "").strip()[:255]
        currency = default_currency
        if currency_col:
            ccy = str(raw.get(currency_col) or "").strip().upper()
            if len(ccy) == 3:
                currency = ccy
        ref = ""
        if ref_col:
            ref = str(raw.get(ref_col) or "").strip()[:120]
        parsed.append((idx, spent, amount, currency, merchant, ref))

    # DE-style signed amount: negatives are spends. If no negatives, treat positives as spends.
    has_negatives = any(a < 0 for _, _, a, _, _, _ in parsed)
    rows: list[BankRow] = []
    for idx, spent, amount, currency, merchant, ref in parsed:
        if has_negatives:
            if amount >= 0:
                continue
            spend = abs(amount)
        else:
            if amount < 0:
                spend = abs(amount)
            else:
                spend = amount
        spend = spend.quantize(Decimal("0.01"))
        if not ref:
            bank_ref = _stable_ref(
                spent_on=spent, amount=spend, merchant=merchant, row_idx=idx
            )
        else:
            bank_ref = f"{filename}:{ref}"[:128]
        note = merchant if merchant else f"Bank import ({filename})"
        rows.append(
            BankRow(
                spent_on=spent,
                amount=spend,
                currency=currency,
                merchant=merchant,
                note=note[:500],
                bank_ref=bank_ref,
            )
        )
    return rows