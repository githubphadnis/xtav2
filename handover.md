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
- GitHub Project (Golden Board) not created yet — issue #5 tracks it

## Next Immediate Steps

1. Confirm Actions CI/GHCR on https://github.com/githubphadnis/xtav2
2. Portainer stack on notcoolio with `OLLAMA_BASE_URL=http://lenai:11434`
3. Cloudflare tunnel hostname + Access
4. Create Golden Board and triage V1.0 issues #1–#5
5. Daily-drive manual logging before enabling OCR flags
