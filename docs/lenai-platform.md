# lenai platform — enhancement backlog

**Status:** infra track — **not** a product feature list.  
**Tracking:** [#15](https://github.com/githubphadnis/xtav2/issues/15)

Products (xtav2 and others) **consume** lenai. This doc is about making the
**host / Ollama / agent layer** good enough for many apps.

## Why separate from products?

| Product work (e.g. xtav2) | Platform work (lenai) |
|---------------------------|------------------------|
| Schema, OCR, Ask filters | Model inventory & sizing |
| Domain tools (`query_spend`) | Tool-calling runtime / gateway |
| UI, flags, deploy of the app | Capacity, concurrency, health |
| Privacy toggle for Vision | Who may reach `:11434` |

Without platform investment, every app reinvents “chat with my data” poorly.

## Current baseline (Jul 2026)

- Host: `lenai` — Ollama at `http://lenai:11434` (from notcoolio stack network)
- Chat used by xtav2: `qwen2.5:14b` (must exist on inventory)
- Vision (optional): `minicpm-v` — privacy fallback only; Google preferred for OCR text
- Pattern so far: **app builds aggregates → model rephrases** (not full agent loop)

## Enhancement themes

### 1. Inventory & policy
- Living list of models (chat / vision / embed) with verified names
- Never default an unverified `OLLAMA_MODEL` in any product
- Document VRAM budget and which models can coexist

### 2. Capacity & reliability
- Concurrent request behaviour under multi-product load
- Timeouts / queueing when a long OCR or Ask holds the GPU
- Health probes beyond `/api/tags` (loaded model, recent errors)

### 3. Agent / tool-calling layer
- Enable Ollama tool-calling (or a thin gateway) so products register tools
- Shared session/memory story (optional; start without)
- Optional **MCP hub**: products expose tools; Cursor and apps both use them

### 4. Security
- Bind Ollama to private network only (already the intent)
- Auth or network ACL if more hosts need access
- No public Cloudflare tunnel to Ollama

### 5. Upgrade path
- When hardware allows: larger chat model for better NL + tool use
- Separate vision vs chat so one load does not starve the other

## Relationship to xtav2 Ask

xtav2 should move toward **tool-calling over Postgres** (product issue / milestone).
That work **depends on** lenai supporting reliable tool-capable models and load —
tracked here as platform prerequisites, implemented in the app separately.

## Out of scope here

OCR providers, expense schema, mass upload, Cloudflare Access for the web UI —
see product issues (#9, #14, etc.).
