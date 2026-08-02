# Handover — xtav2

## Last Worked On Date

2026-08-02 — **STOP**. Insights OK in prod; **Ask still poor**. Docs synced; no further Ask work this session.

## Live

- **URL:** https://xta.pphadnis.com/
- **Repo:** https://github.com/githubphadnis/xtav2 · branch `main`
- **Image:** `ghcr.io/githubphadnis/xtav2:main` (deploy ≥ `6983437`)

## Current State

### Operator verdict (2026-08-02)

| Area | Verdict |
|------|---------|
| Insights (#29) | **OK** — top shops 3mo, top items 6mo |
| Mass rename (#28) | Working |
| **Ask** | **Still shite** — patches (line-SKU, word-boundary, clarify) help edge cases only; do not trust for daily use |

### Shipped this session (code on `main`)

| Area | Commit / notes |
|------|----------------|
| Mass rename #28 | `3e71123` |
| Ask line-SKU / multi-word | `3a9c616` |
| Ask word-boundary + clarify; Insights windows | `a791ac8` |
| CI lint fix + docs | `6983437` |
| Rule 17 | Ledger-first Ask; RAG not default |

### Portainer flags

```env
FEATURE_TRENDS_UI=true
FEATURE_BANK_IMPORT=true
FEATURE_RECEIPT_OCR=true
FEATURE_LINE_ITEMS=true
FEATURE_OCR_GOOGLE_VISION=true
FEATURE_MASS_RENAME=true
PRIVACY_LOCAL_ONLY=false
GOOGLE_VISION_API_KEY=<secret>
```

## Broken Things / Known gaps

1. **Ask quality** — primary open product pain; verify via Expenses; see `docs/ask.md`
2. Bank PDF not supported — CSV only at Settings → `/bank`
3. Capture = receipt **images** only (not statements)
4. #9 mass upload, #14 security, #15 lenai, #23 cloud Ask — open
5. No SSH from agent to notcoolio — LAN `:4280` / Portainer console for ops
6. Mass rename has **no undo**

## Next Immediate Steps (next session)

1. **Ask quality** as dedicated work — exact failing phrases from prod; deterministic intents / UI honesty first (Rule 17). Do **not** start with RAG.
2. Bulk Pending [#26] / bulk delete [#25] when UX priority returns.
3. Optional cloud Ask [#23] only with privacy gate.

## Key doc index

| Doc | Purpose |
|-----|---------|
| `docs/ask.md` | Ask reality check + pipeline + failure classes |
| `docs/insights.md` | Pulse + top shops (3mo) + top items (6mo) |
| `docs/feature-flags.md` | Includes `FEATURE_MASS_RENAME` |
| `agent_rules.md` Rule 17 | Ledger Q&A integrity |
| `handover.md` | This file |
| `BREADCRUMBS.md` | Session trail |
| `ROADMAP.md` | Issues / phases |
| `CHANGELOG.md` | Unreleased notes |
