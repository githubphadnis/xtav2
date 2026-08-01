# Ask — natural-language spend Q&A

**Status:** usable for **simple** questions; quality is often poor for complex NL.  
**Flag:** `FEATURE_OLLAMA_QA` → `/ask`  
**Code:** `app/services/expenses.py` (parse + aggregates), `app/services/ask_agent.py` (Ollama tools)  
**Related:** [#23](https://github.com/githubphadnis/xtav2/issues/23) optional cloud LLM / better voice

## Honest quality note

Ask responses have been **wrong or nonsense** in prod (e.g. invented Google totals,
random line items for “average spend”). Treat Ask as a **helper**, not truth.

**Source of truth:** Expenses list filters (and Insights for MoM). Always verify
suspicious Ask numbers by opening Expenses with the same merchant/date window.

## How it actually works

```
Question
   │
   ├─1─ parse_ask_query  → merchant / category / tokens / period / intent
   ├─2─ query_spend      → Postgres aggregate (duplicates + family/savings excluded)
   ├─3─ try_deterministic_answer  → if clear, return (no LLM)
   └─4─ else Ollama tool loop / fallback  → may still mangle phrasing
```

The button says “Ask Ollama”, but **ledger filters run first**. Ollama mostly
rephrases tool/aggregate JSON. Bad parse → bad aggregate → bad answer (LLM or not).

## What works reasonably

| Phrase shape | Example |
|--------------|---------|
| Merchant + optional year | `How much did I spend on Google in 2025?` |
| Merchant with `at` / `on` | `How much at REWE this month?` |
| Category alias | `How many times did I go to the shops?` |
| Product synonym | `How much on Schokolade?` / kebab ↔ Döner |
| Top-N items | `top 5 most expensive items this month` |

Periods understood: `this month`, `last month`, `this year` / `ytd`, `this week`,
and calendar year `in 2025` / `2025`.

Non-spend bank categories (`family`, `savings`) are **excluded** from totals
(see `docs/bank-reconcile.md`).

## What does not work (yet)

| Ask | What happens |
|-----|----------------|
| Average per month / week | Deterministic refuse — not implemented |
| Vague / multi-part questions | Often junk tokens or Ollama hallucination |
| Bank PDF / Capture for statements | Wrong UI — use Settings → `/bank` CSV |
| Trusting “116 visits / 2764 EUR” style claims | **Verify in Expenses** |

## How to verify any Ask answer

1. Note merchant + dates implied by the question.
2. Open Expenses: `/?merchant=Google&start=2025-01-01&end=2025-12-31` (example).
3. Sum rows on screen — that is ground truth.
4. If Ask ≠ list, Ask is wrong; file/fix parse rules with the **exact user phrase**.

## Failure classes already encoded

- Whole-sentence ILIKE → tokenize first
- `%am%` / `%per%` from stopwords → expanded stop list + prefer merchant totals
- `Wh**at was**` → `\b` before `at|on|…`
- `on Google` vs `on Schokolade` → merchant vs product synonym
- Invented averages → refuse until a real aggregate exists

## Future

- Stronger deterministic intents (monthly average, MoM, budget)
- Optional cloud LLM (#23) with privacy gate
- UI: show “from ledger” vs “Ollama phrasing” so users know what ran
