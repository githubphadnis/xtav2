# Insights surface (product design)

**Status:** design only — no UI yet  
**Tracks:** [#20](https://github.com/githubphadnis/xtav2/issues/20) analytics,
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

One mobile **Insights** home (not four apps). Ask stays the dig tool; charts stay
grounded in the **same Postgres aggregates** Ask tools use.

## Phases

### Phase 1 — Pulse (#20, `FEATURE_TRENDS_UI`)

Answers **A** and enough of **C** for glanceable totals.

- This month total vs last month (base currency)
- Category breakdown (month)
- Top merchants (month)
- Tap slice → filtered ledger **or** Ask with preloaded question + aggregate

### Phase 2 — Coach (#23 + `FEATURE_SAVINGS_INSIGHTS`)

Answers **B** with warmth (not cold charts alone).

- 1–3 suggested cuts from real aggregates (“restaurants +18% MoM”)
- Optional cloud LLM for tone; never invents amounts
- Privacy local-only blocks cloud

### Phase 3 — Habits (#22)

Answers **D** at product level.

- Categories on **line items** (auto + manual fix)
- Visual: this month’s line-item category mix
- Ask: “how much on chocolate / snacks?”

Depends on solid Capture + confirm coverage (bank-only rows stay header-only).

### Phase 4 — Place (#21, `FEATURE_GEO`)

Extends **D** / travel **C**.

- Prefer city/region from receipt text before map tiles
- Geocoding optional; blocked when privacy local-only
- Skip full map until city data exists on enough rows

## Non-goals (for Insights v1)

- Multi-widget BI dashboard
- Separate analytics DB
- LLM-invented charts
- Geo as a day-one requirement

## Shared contract

```
Insights UI  ─┐
Ask agent    ─┼─→ expense aggregate / breakdown services → Postgres
MCP tools    ─┘
```

Definition of done for any chart: same number as `query_spend` / MCP for that filter.
