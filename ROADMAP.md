# Roadmap — xtav2

## V1.0 — Live ledger + ask + MCP

**Target:** first Portainer deploy behind Cloudflare; personal use daily.

### Themes

- Mobile-first manual capture
- Multi-currency base conversion
- Ollama Q&A over real rows
- MCP tools for Cursor / agents
- Feature-flag skeleton for all future inputs

### Included

- Manual CRUD + list/filter
- Postgres store
- Ollama on `lenai`
- MCP server process (or sidecar)
- GHCR + Portainer + Cloudflare path

### Explicitly Excluded

- OCR, bank import, email, savings engine, charts — see manifest

### Milestones

| Milestone | Goal |
|-----------|------|
| V1.0 | Live on notcoolio; daily manual logging + ask + MCP |
| V1.1 | Receipt OCR (Ollama vision) + bank CSV; Google Vision optional flag |
| V1.2 | Email ingest + line items + savings insights |
| V2.0 | Trends UI, geo, public docs site polish |

---

## V1.1 — Inputs

- Receipt photo → structured expense (Ollama vision first)
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
