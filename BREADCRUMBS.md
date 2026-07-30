# Breadcrumbs — xtav2

## Session: 2026-07-30 (Expenses rename + reimport CLI)

- Renamed user-facing **Ledger → Expenses** (nav, page title, Insights buttons).
- Added `python -m app.tools.reimport_receipts` for wipe + re-OCR from uploads (#24).
- **Not pushed yet** — need commit/push → GHCR → Portainer → dry-run → wipe --ocr --yes.
- Wipe deletes all expenses (manual/bank too); keeps `xtav2_uploads` volume.

## Session: 2026-07-29 (personal planning → daily_schedule)

- Personal schedule/printables moved out of xtav2 into local project
  `C:\projects\daily_schedule` (no GitHub remote yet).
- Removed `docs/personal/` from this repo; xtav2 stays product-only.

## Session end: 2026-07-27 (handoff for tomorrow)

- **Stop point for next chat:** redeploy, verify Insights **3-month rem bars** show,
  then continue from `handover.md` → Next Immediate Steps.
- **Work done today (high level):**
  - Roadmap A–D Insights; #20–#23 issues; Phase 1 `/insights`
  - Bank import #17; CI ruff 0.16 fix; receipt date OCR fix #24
  - Ask top-N expensive items; Insights polish (buttons, rolling 3-mo chart)
  - Chart bug: `%` height → invisible bars; switched to `bar_height_rem`
- **Branch:** `main` (push after this docs+chart fix commit)
- **Do not forget:** Portainer `FEATURE_TRENDS_UI=true`; old dates may still be wrong

## Session: 2026-07-27 (insights polish + top-N ask)

- Insights visuals + Ask top-N; then rolling 3-mo chart without rank bullets.
