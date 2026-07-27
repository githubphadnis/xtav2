# Handover — xtav2

## Last Worked On Date

2026-07-27 (evening) — stop here for next session

## Live

- **URL:** https://xta.pphadnis.com/
- **Repo:** https://github.com/githubphadnis/xtav2 · branch `main`
- **Image:** `ghcr.io/githubphadnis/xtav2:main` (pull after CI green)

## Current State / WIP

### Working on main (recent commits)

| Area | Flag / route | Notes |
|------|----------------|-------|
| Bank CSV reconcile | `FEATURE_BANK_IMPORT` → `/bank` | #17 — link/enrich, Ask counts once |
| Insights Phase 1 | `FEATURE_TRENDS_UI` → `/insights` | #20 — MoM, 3-mo chart, category/merchant |
| Receipt dates | OCR path | #24 — printed `Datum` > LLM > `date:unparsed` |
| Ask top-N | `FEATURE_OLLAMA_QA` | “top 5 most expensive items this month” deterministic |
| FX | `FEATURE_MULTI_CURRENCY` | Frankfurter/ECB → `amount_base` (#19 shipped) |
| Duplicates | always on for posted | #16 — fingerprint; not bank↔receipt |

### Portainer flags to enable (if not already)

```env
FEATURE_TRENDS_UI=true
FEATURE_BANK_IMPORT=true          # if using statements
FEATURE_RECEIPT_OCR=true
FEATURE_LINE_ITEMS=true
FEATURE_OCR_GOOGLE_VISION=true
PRIVACY_LOCAL_ONLY=false          # + Settings UI privacy off for Google
GOOGLE_VISION_API_KEY=<secret>
```

Confirm: `GET /health/flags` and Settings “Google Vision effective = yes”.

## Broken Things / Known gaps

1. **Insights 3-month chart looked empty** — CSS `%` bar height collapsed; fixed to
   `rem` heights in latest commit — **redeploy** before judging visuals.
2. **Existing `spent_on` rows** may still be upload-day from before #24 — need
   manual edit or re-OCR repair (#24 remaining work).
3. **Ask tone** cold / hit-miss — #23 optional cloud LLM + savings coach.
4. **#9 mass upload** parked (`docs/mass-ingest.md`).
5. **#14 security**, **#15 lenai platform** open.
6. Rank bullets removed from Insights lists (user request); chart peaks show amounts.

## Product decisions locked

- Insights goals **A–D all in scope** — phased in `docs/insights.md`.
- Bank + receipt = **enrich one row**, never double-count (#17 vs #16).
- Spend date = **printed receipt**, never silent upload day (#24 + agent_rules).

## Next Immediate Steps (tomorrow)

1. Pull latest `main` / redeploy Portainer image.
2. Open Insights — confirm **3 vertical bars with € peaks** visible.
3. Spot-check a new Capture: Pending date matches receipt `Datum`.
4. Ask: `top 5 most expensive items this month` (needs line items).
5. Optional: #24 re-OCR repair for old wrong dates; then Phase 2 (#23) or #17 smoke.

## Key doc index

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | Entrypoint |
| `docs/insights.md` | Insights design + chart note |
| `docs/bank-reconcile.md` | Bank↔receipt rules |
| `docs/receipts.md` | OCR + spend date rules |
| `docs/feature-flags.md` | All `FEATURE_*` |
| `docs/deploy-portainer.md` | Deploy |
| `BREADCRUMBS.md` | Session trail |
| `ROADMAP.md` | Issues / phases |
| `CHANGELOG.md` | Unreleased notes |
