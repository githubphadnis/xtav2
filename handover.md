# Handover — xtav2

## Last Worked On Date

2026-07-27

## Current State / WIP

- **Live:** https://xta.pphadnis.com/
- **#17 bank import** on `main` — `FEATURE_BANK_IMPORT=true` in Portainer to use.
- **#20 Insights Phase 1** built — `/insights` behind `FEATURE_TRENDS_UI` (default off).
- Later Insights: Phase 2 #23, Phase 3 #22, Phase 4 #21 (`docs/insights.md`).

## Broken Things / Known gaps

- Ask tone still hit-and-miss — Phase 2 / #23.
- #17 / #20 need Portainer flag smoke before closing issues.

## Next Immediate Steps

1. Redeploy GHCR image after push.
2. Portainer: `FEATURE_TRENDS_UI=true` (+ `FEATURE_BANK_IMPORT=true` if using bank).
3. Smoke `/insights` + tap category → ledger.
4. Phase 2 when ready (#23 + savings hints).
