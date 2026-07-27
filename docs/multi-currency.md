# Multi-currency

**Flag:** `FEATURE_MULTI_CURRENCY` (default `true`)  
**Base:** `BASE_CURRENCY` (default `EUR`)  
**Rates:** Frankfurter / ECB via `FX_API_BASE_URL` (default `https://api.frankfurter.app`)

## Behaviour

1. Store **original** `amount` + `currency` on every expense.
2. When multi-currency is on, also store `amount_base` in `BASE_CURRENCY` using the
   rate for `spent_on` (weekend → previous ECB publish day).
3. Ask / `query_spend` totals use **`amount_base`** (foreign rows without a rate
   are omitted from the sum until converted).
4. Optional **FX rate override** on Add (manual) when the API lacks a pair
   (e.g. some non-ECB currencies like INR — use override).

## Health

`GET /health/fx` — probes the rate API with a sample pair.

## UI

- Currency dropdown on Add / Pending
- Ledger shows `≈ base` under foreign amounts
