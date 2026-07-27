# Handover — xtav2

## Last Worked On Date

2026-07-27

## Current State / WIP

- **Live:** https://xta.pphadnis.com/
- **#17 bank import** implemented on working tree (not necessarily pushed): CSV → create
  or link; receipt confirm enriches bank row. Flag `FEATURE_BANK_IMPORT` (default off).
- Roadmap queued: #20 analytics, #21 geo, #22 line-item cats, #23 optional public LLM.

## Broken Things / Known gaps

- Ask tone still hit-and-miss on local Ollama — tracked as #23 (cloud LLM option).
- #17 needs Portainer flag + real CSV smoke before closing the issue.

## Next Immediate Steps

1. Commit/push when ready; redeploy GHCR image.
2. Portainer: `FEATURE_BANK_IMPORT=true` → Settings → Import bank CSV.
3. Smoke: bank-only row → Capture matching receipt → Confirm → one ledger row with line items.
4. Decide on #23 (OpenAI/Anthropic behind privacy toggle) vs tuning lenai (#15).
