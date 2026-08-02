# Insights surface

**Status:** Phase 1 live behind `FEATURE_TRENDS_UI` → `/insights`  
**Code:** `app/services/insights.py`, `app/templates/insights.html`, `app/static/app.css`  
**Tracks:** [#20](https://github.com/githubphadnis/xtav2/issues/20) (pulse),
[#22](https://github.com/githubphadnis/xtav2/issues/22) line-item categories,
[#21](https://github.com/githubphadnis/xtav2/issues/21) geo,
[#23](https://github.com/githubphadnis/xtav2/issues/23) Ask voice,
`FEATURE_SAVINGS_INSIGHTS`

## Goals (all in scope)

| ID | User want | Primary surface |
|----|-----------|-----------------|
| **A** | Am I overspending this month? | MoM / budget pulse |
| **B** | What should I cut? | Savings hints + top leaks |
| **C** | Where did €X go last week? | Ask + tap-through filters |
| **D** | Habits I don’t notice | Line-item + merchant patterns (+ geo later) |

## What Phase 1 shows today

1. **Hero key message** — MoM comparator text (“You spent X more…”).
2. **Expenses / Ask buttons** on hero and slices (not plain text links).
3. **Rolling 3-month vertical bar chart** — oldest→newest; current month = MTD;
   prior months = full calendar months. Peak labels = `format_money` + currency.
   Tap column → expenses list filtered to that window.
4. **MTD vs same-days-last-month** detail cards.
5. **Category + merchant** horizontal bars (amount at end of bar).
6. **Top 5 shops visited** (by visit count, **last 3 months**) — amount at end of
   horizontal bar ([#29](https://github.com/githubphadnis/xtav2/issues/29)).
7. **Top 10 bought line items** (by frequency, **last 6 months**) — average cost at
   end of bar ([#29](https://github.com/githubphadnis/xtav2/issues/29)).
8. Aggregates use `amount_base` when multi-currency; exclude active duplicates **and**
   non-spend categories (`family` / `savings` — see `docs/bank-reconcile.md`).

### Chart implementation note (2026-07-27)

Vertical bar **height must use absolute `rem`** (`bar_height_rem`), not CSS `%`.
Percentage height on flex children collapsed to ~0 — looked like “no chart”.
Fixed in the handoff commit; redeploy required to see bars.

## Phases

### Phase 1 — Pulse (#20) — **shipped** (polish ongoing)

### Phase 2 — Coach (#23 + `FEATURE_SAVINGS_INSIGHTS`)

Answers **B** with warmth on real aggregates.

### Phase 3 — Habits (#22)

Line-item categories + visual mix. Needs solid OCR line-item coverage.

### Phase 4 — Place (#21, `FEATURE_GEO`)

City/region first; map later. Privacy-aware geocoding.

## Shared contract

```
Insights UI  ─┐
Ask agent    ─┼─→ expense aggregate / breakdown services → Postgres
MCP tools    ─┘
```

DoD for any chart: same number as `query_spend` / MCP for that filter.
