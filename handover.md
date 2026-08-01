# Handover — xtav2

## Last Worked On Date

2026-08-01 — `docs/ask.md` added; project docs synced; session stop (human restart)

## Live

- **URL:** https://xta.pphadnis.com/
- **Repo:** https://github.com/githubphadnis/xtav2 · branch `main`
- **Image:** `ghcr.io/githubphadnis/xtav2:main` (pull through `166ed2d`+)

## Current State / WIP

### Prod (as of end of 2026-07-30 session)

- #24 wipe+reimport done; Pending cleared by user
- Bank CSV re-imported; family/savings transfers tagged (#27)
- Insights in use (July skewed after wipe — expected to normalize)
- Ask: ledger-first; do **not** trust LLM phrasing without Expenses filter check

### Shipped recently

| Area | Notes |
|------|--------|
| Expenses rename | Nav / page / Insights |
| #24 reimport | CLI + `POST /ops/reimport` |
| #27 non-spend | `family` / `savings` excluded from Ask + Insights |
| Ask fixes | `on Google` merchant; year `in 2025`; refuse average; product vs merchant |
| Bulk UX | Tracked only — [#25](https://github.com/githubphadnis/xtav2/issues/25) delete, [#26](https://github.com/githubphadnis/xtav2/issues/26) approve |

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

1. Ask still weak for averages / complex NL — verify via Expenses filters
2. Bank PDF not supported — CSV only at Settings → `/bank`
3. Capture = receipt **images** only (not statements)
4. #9 mass upload, #14 security, #15 lenai, #23 cloud Ask — open
5. No SSH from agent to notcoolio — LAN `:4280` / Portainer console for ops

## Next Immediate Steps

1. After restart: confirm Portainer image ≥ `166ed2d`; read `docs/ask.md`.
2. Spot-check Ask vs Expenses filter for Google / 2025 if not done.
3. Later: bulk Pending [#26] / bulk delete [#25]; Ask quality / #23.

## Key doc index

| Doc | Purpose |
|-----|---------|
| `docs/ask.md` | Ask: ledger-first, known failures, how to verify |
| `docs/receipts.md` | OCR + reimport |
| `docs/bank-reconcile.md` | Bank CSV + non-spend transfers |
| `docs/insights.md` | Insights phases |
| `handover.md` | This file |
| `BREADCRUMBS.md` | Session trail |
| `ROADMAP.md` | Issues / phases |
| `CHANGELOG.md` | Unreleased notes |
