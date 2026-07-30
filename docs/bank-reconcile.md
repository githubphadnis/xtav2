# Bank ↔ receipt reconcile

**Tracking:** [#17](https://github.com/githubphadnis/xtav2/issues/17)  
**Flag:** `FEATURE_BANK_IMPORT`  
**Status:** implemented (CSV import + enrich on confirm)

## Not the same as #16 duplicates

| Same-source double scan | Bank + receipt |
|-------------------------|----------------|
| Two photos of one receipt | Bank total + receipt detail |
| Flag / delete one | **Map and enrich** — keep both signals on **one** expense row |

## Rules

1. **Receipt first, bank later**  
   Match bank line → existing expense (date ±1 day, amount, merchant overlap).  
   Set `bank_ref`; **do not** create a second posted total. Source → `bank+receipt`.

2. **Bank first, receipt later**  
   On pending **Confirm**, match receipt → bank expense.  
   **Add line items** + receipt image to that row; **delete** the receipt-only draft.  
   Ask counts once.

3. **No match**  
   Create a new expense (bank-only or receipt-only).

## CSV

- Settings → **Import bank CSV** (`/bank`) when the flag is on.
- Headers: date (`Datum` / `Buchungstag` / `date`) + amount (`Betrag` / `amount`).
- Optional: merchant / `Verwendungszweck`, currency, reference.
- Signed files: only **negative** amounts import as spends. All-positive files: all rows as spends.
- Idempotent via `bank_ref` (CSV reference or stable hash).

## Non-spend transfers (family / savings)

Some bank lines are **not household spend** (family support, pocket / loose-change
moves). They stay on the Expenses list but are **excluded from Ask + Insights**.

| Pattern (merchant/note) | Category | Counted as spend? |
|-------------------------|----------|-------------------|
| `Rashmi`, `NRE`, … | `family` | No |
| `pocket`, `Loose Change`, … | `savings` | No |
| Normal merchants | unchanged | Yes |

- Auto-tagged on bank CSV import (`app/services/transfers.py`).
- Reclassify existing rows: `python -m app.tools.reclassify_transfers` (or re-import the same CSV — reclassify runs after import).
- UI shows “Not counted as spend (family|savings)”.

## Fingerprint note

#16 fingerprinting must **not** replace this path. Bank↔receipt uses explicit
reconcile (`app/services/reconcile.py`) so Ask never double-counts.
