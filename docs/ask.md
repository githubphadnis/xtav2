# Ask — natural-language spend Q&A

**Status (2026-08-02):** **Still unreliable in prod.** Operator verdict after recent
patches: Insights OK; **Ask still shite**. Use Expenses filters (and Insights) as
truth. Treat Ask as experimental helper only.

**Flag:** `FEATURE_OLLAMA_QA` → `/ask`  
**Code:** `app/services/expenses.py` (parse + aggregates), `app/services/ask_agent.py` (Ollama tools)  
**Related:** [#23](https://github.com/githubphadnis/xtav2/issues/23) optional cloud LLM / better voice;
`agent_rules.md` **Rule 17** (ledger-first; no RAG for money totals)

## Honest quality note

Ask often returns **wrong, incomplete, or nonsense** answers even for simple-looking
phrases. Recent fixes (line-item fallback, word-boundary, clarify buttons) address
**specific** failure classes only — they did **not** make Ask trustworthy overall.

**Source of truth:** Expenses list filters (and Insights for MoM / shops / items).
Always verify suspicious Ask numbers by opening Expenses with the same
merchant/date/product window.

## How it actually works

```
Question
   │
   ├─1─ parse_ask_query  → merchant / category / tokens / period / intent
   ├─2─ query_spend      → Postgres aggregate (duplicates + family/savings excluded)
   │                      + line_matches (word-boundary preferred over substring)
   ├─3─ try_deterministic_answer
   │      ├─ clear total / line total → canned sentence
   │      ├─ ≥2 distinct line labels → clarify message + choose-one buttons
   │      └─ average intent → honest refuse
   └─4─ else Ollama tool loop / fallback  → may still mangle phrasing
```

The button says “Ask Ollama”, but **ledger filters run first**. Ollama mostly
rephrases tool/aggregate JSON. Bad parse → bad aggregate → bad answer (LLM or not).

### Line items & short tokens

When the entity after `on`/`at` is not a known store header match, Ask searches
**receipt line descriptions**. Matching prefers **whole words** (`\btom\b`) so
`Tom Hardy` hits and `RISPENTOMATE` / `FLASCHENTOM` do not. If several distinct
descriptions still match (e.g. Tom Hardy vs Tom Ford), Ask does **not** sum them:
it shows choose-one buttons that re-POST a more specific question.

## What works reasonably (when lucky)

| Phrase shape | Example |
|--------------|---------|
| Merchant + optional year | `How much did I spend on Google in 2025?` |
| Merchant with `at` / `on` | `How much at REWE this month?` |
| Category alias | `How many times did I go to the shops?` |
| Product synonym | `How much on Schokolade?` / kebab ↔ Döner |
| Renamed line SKU (exact) | `How much on Tom Hardy?` (line total, not full basket) |
| Ambiguous short token | `on Tom` → clarify buttons if multiple whole-word labels |
| Top-N items | `top 5 most expensive items this month` |

Periods understood: `this month`, `last month`, `this year` / `ytd`, `this week`,
and calendar year `in 2025` / `2025`.

Non-spend bank categories (`family`, `savings`) are **excluded** from totals
(see `docs/bank-reconcile.md`).

## What does not work (yet)

| Ask | What happens |
|-----|----------------|
| Average per month / week | Deterministic refuse — not implemented |
| Typos / odd phrasing | Parse often wrong |
| Vague / multi-part questions | Often junk tokens or Ollama hallucination |
| Bank PDF / Capture for statements | Wrong UI — use Settings → `/bank` CSV |
| Trusting any Ask total without checking | **Verify in Expenses** |
| Expecting LLM “smart” disambiguation for everything | Only narrow clarify path exists; rest still brittle |

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
- Renamed line SKU asked as merchant (`on Kevin` / `on Tom Hardy` at EDEKA) → was
  0.00; now line-item fallback when header count is 0; multi-word after `on`/`at`
- Substring `tom` matching tomatoes (`RISPENTOMATE`) → prefer **word-boundary**
  matches; if ≥2 distinct labels remain → Ask clarify buttons (not one blended total)

## Future (priority order — do not skip ahead)

1. **Standard-scenario accuracy** — more deterministic intents; exact-phrase tests from
   prod failures; UI badge “from ledger” vs “Ollama phrasing”. **Next Ask milestone.**
2. **Better tool-calling on lenai** — model/context via inventory (#15); optional cloud
   voice (#23) with privacy gate — still ledger tools first.
3. **Patterns / sinkholes** — Insights depth + flagged savings; charts must match
   `query_spend` (Insights already preferred over Ask for habits).
4. **Optional unstructured retrieval (RAG)** — only if notes/OCR narrative search is a
   tracked, flagged module. **Never** replace SQL totals with vector similarity.
   See `agent_rules.md` Rule 17.
