# Breadcrumbs — xtav2

## Session end: 2026-08-02 (mass rename #28)

- Opened [#28](https://github.com/githubphadnis/xtav2/issues/28) (V1.0); roadmap/manifest/flags updated.
- Implemented find/replace: `app/services/mass_rename.py`, `/rename` UI, Settings link,
  MCP `mass_rename` (`dry_run` default). Fields: merchant, note, line items.
- Tests: `tests/test_mass_rename.py` (8); full suite **52 passed**.
- **Not committed** (await human). Next: review → commit → deploy → phone smoke Settings → Mass rename.
- Env: `FEATURE_MASS_RENAME=true` (default); Portainer should set explicitly after deploy.

## Session end: 2026-08-01 (restart)

- Added `docs/ask.md` (honest: Ask often shit; ledger-first; verify via Expenses).
- Wired into README / handover / ROADMAP / CHANGELOG.
- **Stop:** human restart. Next agent: read `handover.md` + `docs/ask.md`.
- Image target: `main` ≥ `166ed2d` (Ask fixes); docs commit after.

## Session: 2026-08-01 (docs sync)

- Confirmed docs lag: handover still described 108 Pending; Ask trust fixes not in CHANGELOG.
- Synced handover / breadcrumbs / changelog to prod + Ask state.

## Session: 2026-07-30 (Ask trust + CI)

- Ask: `on Google` merchant; stop `%am%` line noise; `\b` before at/on (Wh**at was**);
  calendar year `in 2025`; honest refuse for average/month; product vs merchant for Schokolade.
- CI red then fixed (`166ed2d`); Docker Publish green.
- Verify Google via Expenses filter — Ask 2764€/116 visits was false (~435€ / 16 rows).

## Session: 2026-07-30 (afternoon status)

- Non-spend transfers #27; bulk UX → #25/#26; bank = CSV `/bank` not Capture/PDF.
- Pending cleared by user; bank re-imported.

## Session: 2026-07-30 (ship Expenses + prod #24 wipe)

- Expenses rename + reimport; LAN `/ops/reimport`; 108 OCR → pending then confirmed.

## Session: 2026-07-29 (personal planning → daily_schedule)

- Personal schedule moved to `C:\projects\daily_schedule`; xtav2 product-only.

## Session end: 2026-07-27

- Insights rem bars; receipt date #24; bank #17; Ask top-N.
