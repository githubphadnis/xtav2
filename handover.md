# Handover — xtav2

## Last Worked On Date

2026-07-30 — Expenses rename shipped; #24 wipe+reimport OCR done on prod

## Live

- **URL:** https://xta.pphadnis.com/
- **Repo:** https://github.com/githubphadnis/xtav2 · branch `main`
- **Image:** `ghcr.io/githubphadnis/xtav2:main` (commit `3235eea`+; pull after pending-limit fix)

## Current State / WIP

### Prod after wipe (2026-07-30)

- Expenses wiped (100 rows) + **108** upload images re-OCR’d → all **pending**
- Spot-check: printed dates spread across Jul 18–27 (not upload-day cluster)
- ~2 `date:unparsed` on first Pending page — fix those before confirm
- **You:** confirm Pending queue (badge was capped at 20 — fix pushing), then bank CSV if needed

### Shipped

| Area | Notes |
|------|--------|
| Expenses rename | Nav / page / Insights buttons |
| #24 reimport | CLI + `POST /ops/reimport` (LAN / optional token) |
| Insights / bank / FX / dups | As before |

### Portainer flags

```env
FEATURE_TRENDS_UI=true
FEATURE_BANK_IMPORT=true
FEATURE_RECEIPT_OCR=true
FEATURE_LINE_ITEMS=true
FEATURE_OCR_GOOGLE_VISION=true
PRIVACY_LOCAL_ONLY=false
GOOGLE_VISION_API_KEY=<secret>
```

## Broken Things / Known gaps

1. **108 Pending** await human confirm (printed Datum check).
2. Bank rows wiped — re-import CSV at `/bank` if you still use statements.
3. Ask tone / #23; mass upload #9; security #14; lenai #15.
4. Agent has no SSH key for notcoolio — used LAN `/ops/reimport` after Portainer pull.

## Next Immediate Steps

1. Pull latest image (pending list limit + accurate badge count).
2. Open Pending — confirm dates (fix `date:unparsed` first); work through all 108.
3. Re-import bank CSV if needed; spot-check Insights.
4. Optionally set `OPS_REIMPORT_TOKEN` and treat `/ops/reimport` as token-only.

## Key doc index

| Doc | Purpose |
|-----|---------|
| `docs/receipts.md` | OCR + reimport CLI / `/ops/reimport` |
| `handover.md` | This file |
| `BREADCRUMBS.md` | Session trail |
| `ROADMAP.md` | Issues / phases |
