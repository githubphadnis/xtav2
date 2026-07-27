# Bank ↔ receipt reconcile (design note)

**Tracking:** [#17](https://github.com/githubphadnis/xtav2/issues/17)  
**Status:** not implemented — capture rules before `FEATURE_BANK_IMPORT`.

## Not the same as #16 duplicates

| Same-source double scan | Bank + receipt |
|-------------------------|----------------|
| Two photos of one receipt | Bank total + receipt detail |
| Flag / delete one | **Map and enrich** — keep both signals |

## Rules

1. **Receipt first, bank later**  
   Match bank line → existing expense (date ±1 day, amount, merchant).  
   Link bank ref; **do not** create a second posted total.

2. **Bank first, receipt later**  
   Match receipt → bank expense.  
   **Add line items** + receipt image to that row.  
   Do **not** throw away the receipt as a duplicate.

3. **No match**  
   Create a new expense (bank-only or receipt-only).

## Fingerprint note

#16 fingerprinting must **not** auto-discard a receipt that should enrich a bank row.
Bank import will use an explicit reconcile path (match → enrich) instead of
`duplicate_of_id` alone.
