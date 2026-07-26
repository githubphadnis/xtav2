# Roadmap — xtav2

## V1.0 — Live ledger + ask + MCP

**Target:** first Portainer deploy behind Cloudflare; personal use daily.

### Themes

- Mobile-first manual capture (add + **delete**)
- Multi-currency base conversion
- Ollama Q&A over real rows (model must exist on lenai)
- MCP tools for Cursor / agents
- Feature-flag skeleton for all future inputs

### Included

- Manual CRUD (create, list, **delete**) + filter
- Postgres store
- Ollama on `lenai` (`OLLAMA_MODEL` from live inventory)
- MCP server process (or sidecar)
- GHCR + Portainer + Cloudflare path

### Explicitly Excluded (this milestone)

- Camera / receipt OCR — V1.1
- Mass directory upload — V1.1
- Bank import, email, savings, charts — later

### Open issues (board)

| Issue | Theme |
|-------|--------|
| [#9](https://github.com/githubphadnis/xtav2/issues/9) | Mass upload from directory (init ingest) |
| [#14](https://github.com/githubphadnis/xtav2/issues/14) | Security & compliance hardening |

### Closed (V1.0 / V1.1 partial)

| Issue | Theme |
|-------|--------|
| #1–#3 | CRUD, Ask, MCP |
| #4 | Portainer + Cloudflare (`https://xta.pphadnis.com/`) |
| #5 | Golden Board (deferred OK) |
| #7 / #10 | Delete + Ollama model default |
| #8 | Camera capture |
| #11 | Privacy toggle + Google Vision optional |
| #12 | Multi-screen UI + mobile visual polish |
| #13 | Line items + Google-primary OCR |

### Milestones

| Milestone | Goal |
|-----------|------|
| V1.0 | Live on notcoolio; daily manual logging + delete + ask + MCP |
| V1.1 | Camera capture + mass upload (flagged) + bank CSV; Google Vision optional |
| V1.2 | Email ingest + savings insights |
| V1.x | **Security & compliance hardening** (dedicated iteration — see `docs/security-hardening-backlog.md`) |
| V2.0 | Trends UI, geo, public docs site polish |

---

## V1.1 — Inputs

- **Camera capture** on mobile (`FEATURE_RECEIPT_OCR` + vision provider)
- **Mass upload / directory ingest** for bootstrap (`FEATURE_MASS_UPLOAD`)
- Optional Google Vision flag
- Bank CSV/Excel import with column mapping assist

## V1.2 — Depth

- Email ingest
- Line-item extraction
- Savings / pattern hints (flagged)

## V2.0 — Insights surface

- Historical trends UI
- Geospatial spend map
- Tax/export packs
