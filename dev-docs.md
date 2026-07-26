# Developer Documentation — xtav2

## Architectural Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-26 | New repo `xtav2` (not evolve classic `xta` in place) | Clean cOcO Governed reboot; public goal; avoid carrying unfinished XTA debt |
| 2026-07-26 | FastAPI + mobile-first HTML (HTMX/Tailwind path) | Matches house stack (XTA/monsoon/griham); Portainer-friendly; Cursor-friendly |
| 2026-07-26 | Postgres | Matches XTA + monsoon on notcoolio; multi-user ready for public self-host |
| 2026-07-26 | Ollama on lenai only for V1 LLM | Local-first; latency; no API key required for core |
| 2026-07-26 | MCP server as V1 module | Cursor/agents need structured tools; same services as UI |
| 2026-07-26 | Every feature behind `FEATURE_*` flags | Ship V1 live; enable OCR/bank/email later without forks |
| 2026-07-26 | OCR deferred; Ollama vision before Google Vision | Privacy-aligned; Google Vision optional escape hatch |

## Errors Faced & Solutions

| Date | Error | Solution |
|------|-------|----------|
| 2026-07-26 | `create_project` MCP git init failed (`spawn /bin/sh ENOENT` on Windows) | Created dir + `git init -b main` locally, then `move_agent_to_root` |

## Patterns to Avoid

- Building OCR/email/bank before a daily-use manual ledger is live
- Cloud LLM as the only path for Q&A
- Hardcoding `lenai` / ports in code — use env/config
- Duplicating domain logic in MCP vs HTTP — share services

## Successful Patterns

- cOcO Governed artifacts from day one (manifest, roadmap, breadcrumbs)
- monsoon-style deploy: GHCR image + `docker-compose.portainer.yml`
- Feature flags as config, not scattered `if` comments
