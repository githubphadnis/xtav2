# Handover — xtav2

## Last Worked On Date

2026-07-27

## Current State / WIP

- **Live:** https://xta.pphadnis.com/
- **#17 bank import** on `main` (`f9502aa`) — enable `FEATURE_BANK_IMPORT` in Portainer.
- **Insights:** goals A–D all wanted; design in `docs/insights.md` (Phases 1–4). No UI yet.

## Broken Things / Known gaps

- Ask tone still hit-and-miss on local Ollama — tracked as #23 (cloud LLM option).
- #17 needs Portainer flag + real CSV smoke before closing the issue.

## Next Immediate Steps

1. Portainer: pull new image; `FEATURE_BANK_IMPORT=true`; smoke CSV + receipt enrich.
2. When building Insights: start Phase 1 (#20) per `docs/insights.md`.
3. Phase 2 (#23 + savings) for “what to cut” with warmer voice.
4. Phases 3–4 (#22, #21) after line-item / city data is rich enough.
