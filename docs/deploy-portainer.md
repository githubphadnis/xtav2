# Deploy — Portainer (notcoolio)

## Flow

`git push main` → GitHub Actions (`docker-publish.yml`) →
`ghcr.io/githubphadnis/xtav2:main` → Portainer stack → Cloudflare tunnel.

## Portainer

1. Stacks → Add stack → Git repository
2. Repository: `https://github.com/githubphadnis/xtav2`
3. Compose path: `docker-compose.portainer.yml`
4. Branch: `main`
5. Set stack env vars from `.env.example` (especially `POSTGRES_PASSWORD`,
   `OLLAMA_BASE_URL`, `BASE_CURRENCY`, `FEATURE_*`)

## Hosts

| Host | Role |
|------|------|
| `notcoolio` | Portainer + xtav2 stack |
| `lenai` | Ollama (`OLLAMA_BASE_URL=http://lenai:11434`) |

## Cloudflare

Point a tunnel hostname at the app container port (default `8080`). Prefer
Cloudflare Access for auth before public launch hardening is complete.
