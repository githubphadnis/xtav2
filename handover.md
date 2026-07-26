# Handover — xtav2

## Last Worked On Date

2026-07-26

## Current State / WIP

- Live on notcoolio `:4280` — manual add + list working; Ask tokenizes REWE correctly
- Ollama was 404 on `llama3.2` — set Portainer `OLLAMA_MODEL=qwen2.5:14b` (new image default)
- Delete expense shipping in next image; camera + mass upload tracked #8 #9 (flags off)

## Broken Things

- Ask fails until Portainer `OLLAMA_MODEL` matches lenai inventory
- Cloudflare tunnel / Access may still be pending (#4)
- Golden Board (#5) not wired
- Docker image smoke (#6) not implemented yet

## Next Immediate Steps

1. Portainer: set `OLLAMA_MODEL=qwen2.5:14b`, pull/redeploy `ghcr.io/githubphadnis/xtav2:main`
2. Verify `/health/ollama` → status ok; retry Ask
3. Confirm Delete on recent rows
4. Plan #8 camera + #9 mass upload behind flags
