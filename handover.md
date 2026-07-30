# Handover — xtav2

## Last Worked On Date

2026-07-30 — Expenses rename + #24 reimport CLI (awaiting deploy + wipe on prod)

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

### Local (not pushed yet)

- UI: **Ledger → Expenses** (nav, page, Insights buttons); brand sub “tracker”.
- Operator CLI: `python -m app.tools.reimport_receipts --wipe --ocr --yes` (#24).
  Keeps `xtav2_uploads`; deletes all expense rows. Docs: `docs/receipts.md`.

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

1. **Prod still has upload-day `spent_on`** until wipe+reimport runs on notcoolio.
2. **Ask tone** cold / hit-miss — #23 optional cloud LLM + savings coach.
3. **#9 mass upload** parked (`docs/mass-ingest.md`).
4. **#14 security**, **#15 lenai platform** open.
5. Wipe removes manual + bank rows too — re-import bank CSV after receipts confirmed.

## Product decisions locked

- Insights goals **A–D all in scope** — phased in `docs/insights.md`.
- Bank + receipt = **enrich one row**, never double-count (#17 vs #16).
- Spend date = **printed receipt**, never silent upload day (#24 + agent_rules).
- User-facing list name = **Expenses** (not Ledger).

## Next Immediate Steps

1. Commit + push local changes; wait for GHCR `main` publish.
2. Portainer pull/redeploy; confirm nav says **Expenses**.
3. App container console:
   - `python -m app.tools.reimport_receipts --dry-run`
   - `python -m app.tools.reimport_receipts --wipe --ocr --yes`
4. Pending: verify each printed `Datum`, confirm; re-import bank CSV if used.
5. Spot-check Insights MoM after confirm.

## Key doc index

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | Entrypoint |
| `docs/insights.md` | Insights design + chart note |
| `docs/bank-reconcile.md` | Bank↔receipt rules |
| `docs/receipts.md` | OCR + spend date + **reimport CLI** |
| `docs/feature-flags.md` | All `FEATURE_*` |
| `docs/deploy-portainer.md` | Deploy |
| `BREADCRUMBS.md` | Session trail |
| `ROADMAP.md` | Issues / phases |
| `CHANGELOG.md` | Unreleased notes |
