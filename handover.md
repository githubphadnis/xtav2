# Handover — xtav2

## Last Worked On Date

2026-08-02 — Ask word-boundary + clarify; Insights #29 windows; CI lint fix

## Live

- **URL:** https://xta.pphadnis.com/
- **Repo:** https://github.com/githubphadnis/xtav2 · branch `main`
- **Image:** `ghcr.io/githubphadnis/xtav2:main` (target ≥ `a791ac8` + lint fix commit)

## Current State / WIP

### Prod

- Mass rename (#28) in use
- Ask line-SKU fallback shipped (`3a9c616`); word-boundary + clarify in flight (`a791ac8`, CI was red on unused var)

### Shipped this session

| Area | Notes |
|------|--------|
| Mass rename #28 | Settings → `/rename`; MCP `mass_rename` |
| Ask # line SKU | `on Kevin` / `on Tom Hardy` → line totals when merchant header misses |
| Ask clarify | Whole-word match; ≥2 labels → choose-one buttons (`docs/ask.md`) |
| Insights #29 | Top 5 shops **last 3 months**; Top 10 items **last 6 months** |
| cOcO Rule 17 | Ledger-first Ask; RAG not default (`agent_rules.md`) |

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

1. Ask still weak for averages / complex NL — verify via Expenses filters
2. Bank PDF not supported — CSV only at Settings → `/bank`
3. Capture = receipt **images** only (not statements)
4. #9 mass upload, #14 security, #15 lenai, #23 cloud Ask — open
5. No SSH from agent to notcoolio — LAN `:4280` / Portainer console for ops
6. Mass rename has **no undo**

## Next Immediate Steps

1. Confirm CI/Docker green after lint fix; Portainer pull; smoke Ask `on Tom` + Insights windows.
2. Later: bulk Pending [#26] / bulk delete [#25]; Ask quality / #23.

## Key doc index

| Doc | Purpose |
|-----|---------|
| `docs/ask.md` | Ask pipeline, failure classes, clarify / word-boundary |
| `docs/insights.md` | Pulse + top shops (3mo) + top items (6mo) |
| `docs/feature-flags.md` | Includes `FEATURE_MASS_RENAME` |
| `agent_rules.md` Rule 17 | Ledger Q&A integrity |
| `handover.md` | This file |
| `BREADCRUMBS.md` | Session trail |
| `ROADMAP.md` | Issues / phases |
| `CHANGELOG.md` | Unreleased notes |
