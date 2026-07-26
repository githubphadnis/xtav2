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
   `OLLAMA_BASE_URL`, `BASE_CURRENCY`, `FEATURE_*`, `PRIVACY_LOCAL_ONLY`)
6. Host port defaults to **4280** (`XTAV2_HOST_PORT`) — `8080` is usually
   taken by monsoon/XTA on notcoolio. Point Cloudflare at that host port.

Privacy can also be toggled at runtime on **Settings** (DB override). For good
receipt line items, set:

```text
FEATURE_OCR_GOOGLE_VISION=true
GOOGLE_VISION_API_KEY=<secret>
PRIVACY_LOCAL_ONLY=false
FEATURE_LINE_ITEMS=true
```

Then confirm Settings shows Google Vision effective = yes. Details: [`receipts.md`](./receipts.md).

## Hosts

| Host | Role |
|------|------|
| `notcoolio` | Portainer + xtav2 stack |
| `lenai` | Ollama (`OLLAMA_BASE_URL=http://lenai:11434`) |

## Cloudflare

Point a tunnel hostname at the app container port (default `8080` inside Docker /
`XTAV2_HOST_PORT` on the host). Prefer Cloudflare Access for auth before public
launch hardening is complete.

**Live:** https://xta.pphadnis.com/

## Receipt uploads

Enable `FEATURE_RECEIPT_OCR=true` and ensure the `xtav2_uploads` volume is present
(see `docker-compose.portainer.yml`). Details: [`receipts.md`](./receipts.md).
