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
| [#9](https://github.com/githubphadnis/xtav2/issues/9) | Mass upload — **parked** |
| [#14](https://github.com/githubphadnis/xtav2/issues/14) | Security & compliance hardening |
| [#15](https://github.com/githubphadnis/xtav2/issues/15) | **lenai platform** (infra) |
| [#16](https://github.com/githubphadnis/xtav2/issues/16) | Duplicate detection — **shipped** |
| [#17](https://github.com/githubphadnis/xtav2/issues/17) | Bank↔receipt reconcile + enrich line items |
| [#19](https://github.com/githubphadnis/xtav2/issues/19) | Multi-currency FX — **shipped** |
| [#20](https://github.com/githubphadnis/xtav2/issues/20) | Insights Phase 1 pulse — **shipped** (enable `FEATURE_TRENDS_UI`; redeploy for 3-mo bars) |
| [#21](https://github.com/githubphadnis/xtav2/issues/21) | Geographic spend map |
| [#22](https://github.com/githubphadnis/xtav2/issues/22) | Line-item categories + visual breakdown |
| [#23](https://github.com/githubphadnis/xtav2/issues/23) | Optional public/cloud LLM for Ask |
| [#24](https://github.com/githubphadnis/xtav2/issues/24) | Pattern: receipt date ≠ upload day — **repair path shipped**; Pending confirm on prod |
| [#25](https://github.com/githubphadnis/xtav2/issues/25) | Bulk delete expenses / Pending |
| [#26](https://github.com/githubphadnis/xtav2/issues/26) | Bulk approve Pending |
| [#27](https://github.com/githubphadnis/xtav2/issues/27) | Non-spend transfers (`family` / `savings`) — **shipped** |
| [#28](https://github.com/githubphadnis/xtav2/issues/28) | Mass rename find/replace (merchant / note / line items) |

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
| Infra | **lenai platform** — models, capacity, tool-calling runtime (`docs/lenai-platform.md`, #15) |
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

One mobile **Insights** product covering goals A–D (see `docs/insights.md`):

| Phase | Issue | Goal |
|-------|-------|------|
| 1 Pulse | [#20](https://github.com/githubphadnis/xtav2/issues/20) | A + glance C — MoM, category, merchant |
| 2 Coach | [#23](https://github.com/githubphadnis/xtav2/issues/23) + savings flag | B — what to cut (warm Ask on real aggregates) |
| 3 Habits | [#22](https://github.com/githubphadnis/xtav2/issues/22) | D — line-item categories + visual mix |
| 4 Place | [#21](https://github.com/githubphadnis/xtav2/issues/21) | D/C travel — cities first, map later |

- Tax/export packs (separate)

## Ask quality (cross-cutting)

- See [`docs/ask.md`](./docs/ask.md) and `agent_rules.md` **Rule 17** — ledger-first;
  standard phrases must match Expenses/`query_spend`; RAG only for optional flagged
  unstructured search, never for money totals.
- Optional public/cloud LLM beside Ollama ([#23](https://github.com/githubphadnis/xtav2/issues/23)) — Insights Phase 2 voice; privacy toggle must block cloud when local-only
