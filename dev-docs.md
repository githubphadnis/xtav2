# Developer Documentation — xtav2

## Architectural Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-08-02 | Rule 17: ledger Q&A integrity — SQL-first Ask; RAG only flagged unstructured | Ask failures were parse/aggregate, not missing vectors; avoid token waste |
| 2026-08-02 | Mass rename find/replace (#28); no undo; never log find/replace strings | Privacy-adjacent ledger hygiene; sensitive terms |
| 2026-07-30 | Ask ledger-first; merchant `\b`; year YYYY; refuse average | Exact user phrases; verify via Expenses filter |
| 2026-07-30 | Non-spend `family`/`savings` excluded from Ask/Insights | #27; bank auto-tag |
| 2026-07-30 | Operator wipe+reimport (CLI + LAN `/ops`) | #24; prefer OPS token later |
| 2026-07-30 | Ask “on Google” → merchant filter; stop short token OR on lines | Production-Path: exact user phrase test |
| 2026-07-27 | Receipt spent_on from printed OCR, not upload day | Rule 15 + #24; agent_rules |
| 2026-07-27 | Insights vertical bars use rem height not % | % height collapsed in flex layout |
| 2026-07-26 | New repo `xtav2` (not evolve classic `xta` in place) | Clean cOcO Governed reboot; public goal; avoid carrying unfinished XTA debt |
| 2026-07-26 | FastAPI + mobile-first HTML (HTMX/Tailwind path) | Matches house stack (XTA/monsoon/griham); Portainer-friendly; Cursor-friendly |
| 2026-07-26 | Postgres | Matches XTA + monsoon on notcoolio; multi-user ready for public self-host |
| 2026-07-26 | Ollama on lenai only for V1 LLM | Local-first; latency; no API key required for core |
| 2026-07-26 | MCP server as V1 module | Cursor/agents need structured tools; same services as UI |
| 2026-07-26 | Every feature behind `FEATURE_*` flags | Ship V1 live; enable OCR/bank/email later without forks |
| 2026-07-26 | OCR deferred; Ollama vision before Google Vision | Privacy-aligned; Google Vision optional escape hatch |
| 2026-07-26 | Normalize `postgresql://` → `postgresql+psycopg://` | Same monsoon fix — plain URL loads missing psycopg2 |
| 2026-07-26 | Rule 15 Production-Path Parity + Rule 16 Rule Promotion | Encode XTAv2 Portainer failure classes into cOcO so they cannot silently recur |

## Errors Faced & Solutions

| Date | Error | Solution |
|------|-------|----------|
| 2026-07-30 | Ask Google / average / Wh'at was / %per% junk | Merchant `\b`, year bounds, refuse average, product vs merchant |
| 2026-07-30 | CI fail: on Schokolade as merchant | Product synonym after “on” → tokens/line items |
| 2026-07-27 | Insights 3-mo chart invisible | CSS `%` bar height → use `bar_height_rem` |
| 2026-07-27 | Receipt dates = upload day | OCR `Datum` parse first; never silent today; #24 |
| 2026-07-27 | CI fail after FX/bank | Pin ruff 0.16.x + lint cleanups |
| 2026-07-27 | Ask “top expensive items” generic | Deterministic `top_expensive` + month window |
| 2026-07-26 | `create_project` MCP git init failed (`spawn /bin/sh ENOENT` on Windows) | Created dir + `git init -b main` locally, then `move_agent_to_root` |
| 2026-07-26 | Portainer: `No module named psycopg2` | Normalize DB URL to `postgresql+psycopg://` |
| 2026-07-26 | Ask: whole-sentence ILIKE → total 0 | Tokenize NL queries; test exact user phrases first |
| 2026-07-26 | Ollama 404 on `/api/chat` | Model name missing; `/health/ollama` + actionable error |

## Patterns to Avoid

- Building OCR/email/bank before a daily-use manual ledger is live
- Cloud LLM as the only path for Q&A
- Hardcoding `lenai` / ports in code — use env/config
- Defaulting receipt `spent_on` to upload/OCR day when a printed date exists
- CSS percentage heights on flex children for “charts” (use rem/px)
- Duplicating domain logic in MCP vs HTTP — share services
- Shipping after SQLite-only CI when prod is Postgres
- Treating DNS/ping as proof that Ollama/model works

## Successful Patterns

- cOcO Governed artifacts from day one (manifest, roadmap, breadcrumbs)
- monsoon-style deploy: GHCR image + `docker-compose.portainer.yml`
- Feature flags as config, not scattered `if` comments
- Promote recurring failures into scaffolding rules + Cursor user rules
