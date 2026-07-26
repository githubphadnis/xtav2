# AGENTS.md — xtav2

Canonical, tool-agnostic entrypoint for agents working on **xtav2** — reboot of
XTA: self-hosted multi-currency expense tracker with Ollama (lenai) and MCP.

**Governance tier:** Governed (public open-source goal)

**Repo:** https://github.com/githubphadnis/xtav2

## Read order

`AGENTS.md` → `project-manifest.md` → `README.md` → `dev-docs.md` → `handover.md` → `ROADMAP.md`

## Code truth

- **V1 scope:** manual ledger + multi-currency + Ollama Q&A + MCP — not every
  ingestion path. See `project-manifest.md`.
- **Source of truth:** Postgres.
- **LLM:** Ollama on `lenai` (`OLLAMA_BASE_URL`). No cloud LLM required for V1.
- **MCP:** first-class interface alongside the mobile web UI; same domain services.
- **Feature flags:** every module behind `FEATURE_*` env flags — see
  `docs/feature-flags.md`.
- **UI:** mobile-first is non-negotiable.
- **Deploy:** GitHub Actions → `ghcr.io/githubphadnis/xtav2` → Portainer on
  `notcoolio` → Cloudflare. See `docs/deploy-portainer.md`.
- **Prior art:** classic XTA at `C:\projects\xta` / `githubphadnis/xta` — reboot,
  do not edit that tree from this repo.

## Dev server

```bash
cp .env.example .env
docker compose up --build
# App: http://127.0.0.1:8080/health/live
```

| URL / check | Purpose |
|-------------|---------|
| `GET /health/live` | Process up |
| `GET /health/db` | Postgres reachable |
| `GET /health/flags` | Feature flag snapshot |
| MCP stdio / SSE | Agent tools (when `FEATURE_MCP=true`) |

## Rules

- **Style:** [`CODING_GUIDELINES.md`](./CODING_GUIDELINES.md)
- **Process / governance:** [`agent_rules.md`](./agent_rules.md)

## Session contract

1. Read the docs above before changing anything.
2. Follow style + process rules while working.
3. At session end: update `BREADCRUMBS.md` (always); update `handover.md` /
   `dev-docs.md` / `CHANGELOG.md` when state changed. Do not commit/push unless
   asked.
4. **Governed:** board/issues/milestones stay in sync with work; no untracked
   features.

## Canonical artifacts

`project-manifest.md`, `README.md`, `dev-docs.md`, `handover.md`, `BREADCRUMBS.md`,
`ROADMAP.md`, `CHANGELOG.md`.
