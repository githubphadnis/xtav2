# Handover — xtav2

## Last Worked On Date

2026-07-26

## Current State / WIP

- New repo bootstrapped under cOcO **Governed** at `C:\projects\xtav2`
- V1 skeleton: FastAPI mobile UI, Postgres, feature flags, expense services,
  Ollama ask path, MCP server module, Portainer compose, CI/GHCR workflows
- Classic XTA left untouched at `C:\projects\xta`

## Broken Things

- Not yet deployed to notcoolio / Cloudflare
- FX conversion for foreign currencies is stubbed (same-currency only)
- Ollama Q&A uses text filter + aggregate JSON (not full text-to-SQL yet)
- GitHub Project board / milestones not created yet (Governed follow-up)
- First commit / public GitHub remote may still be pending human push

## Next Immediate Steps

1. Commit + create public GitHub repo `githubphadnis/xtav2` and push `main`
2. Confirm Actions build; make GHCR package visible as needed for public
3. Portainer stack on notcoolio with `OLLAMA_BASE_URL=http://lenai:11434`
4. Cloudflare tunnel hostname + Access
5. Open V1.0 milestone issues on the Golden Board
