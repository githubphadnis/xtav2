# xtav2

Self-hosted **expense tracker** (XTA reboot): multi-currency ledger, mobile-first
UI, Ollama Q&A on **lenai**, and an **MCP server** for Cursor/agents.

**Governance:** cOcO Governed · **Deploy:** GitHub → GHCR → Portainer (`notcoolio`) → Cloudflare

## Prerequisites

- Docker / Docker Compose
- (Dev) Python 3.12+
- Access to Ollama on `lenai` (or local Ollama for smoke tests)
- (Prod) Portainer on `notcoolio` + Cloudflare tunnel

## Quick start (local)

```bash
cp .env.example .env
docker compose up --build
curl http://127.0.0.1:8080/health/live
```

Open http://127.0.0.1:8080/ on a phone-width viewport.

## Architecture Overview

```
Mobile browser ──► xtav2 (FastAPI) ──► Postgres
                         │
                         ├── Ollama (lenai) for Q&A / (later) vision OCR
                         └── MCP server (same domain services)
```

All optional inputs (OCR, bank, email, savings) are **feature-flagged**.
See `docs/feature-flags.md`, `docs/mcp.md`, `docs/deploy-portainer.md`.

## Modules (flags)

| Module | Flag | Entry |
|--------|------|--------|
| Ledger / Add | `FEATURE_MANUAL_ENTRY` | `/`, `/add` |
| Capture / Pending | `FEATURE_RECEIPT_OCR` | `/capture`, `/pending` |
| Ask | `FEATURE_OLLAMA_QA` | `/ask` |
| Insights | `FEATURE_TRENDS_UI` | `/insights` |
| Bank CSV | `FEATURE_BANK_IMPORT` | `/bank` (via Settings) |
| MCP | `FEATURE_MCP` | stdio / SSE process |

Design notes: `docs/insights.md`, `docs/receipts.md`, `docs/bank-reconcile.md`.  
**Agent handoff:** start at `handover.md` + `BREADCRUMBS.md`.

## Deployment Steps

1. Push to `main` → GitHub Actions builds `ghcr.io/githubphadnis/xtav2:main`
2. **Smoke job** runs the image against Postgres and hits `/health/*`
3. Portainer stack uses `docker-compose.portainer.yml`
4. Cloudflare Access / tunnel fronts the app — live: https://xta.pphadnis.com/

## Project Structure

```
xtav2/
├── app/                 # FastAPI app + domain services
├── mcp_server/          # MCP entrypoint (FEATURE_MCP)
├── docs/                # Architecture & ops docs
├── tests/
├── docker-compose.yml
├── docker-compose.portainer.yml
├── Dockerfile
├── project-manifest.md
├── AGENTS.md
└── ROADMAP.md
```

## Relationship to classic XTA

Classic XTA remains at `githubphadnis/xta`. This repo is a clean reboot under
cOcO Governed rules — cherry-pick lessons, do not bind the trees.
