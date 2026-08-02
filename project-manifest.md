# xtav2

## Purpose

**xtav2** is the reboot of [XTA](https://github.com/githubphadnis/xta) — a
**secure, self-hosted expense tracker** for capturing *all* spending (manual,
receipts, statements, email), answering natural-language questions over that
data via **Ollama on lenai**, and exposing the same capabilities to agents
through an **MCP server**.

Built to go **public** (open-source product), while remaining deployable on a
home lab: GitHub → GHCR → Portainer (`notcoolio`) → Cloudflare.

## Target Audience / Personas

1. **Household operator** — logs expenses on mobile; asks “how much on crisps
   this quarter?”
2. **Cursor / agent operator** — uses MCP tools against the same store.
3. **Public adopter** — self-hosts via Docker/Portainer (Governed release path).

## Business Value

- One durable ledger for every expense and incidental.
- Multi-currency truth without spreadsheet glue.
- Local LLM insights without shipping receipts to a public SaaS by default.
- Modular inputs behind feature flags so the product can ship before every
  ingestion path is perfect.

## V1 Scope (Initial Boundary)

**Included (flags ON by default):**

- Manual expense entry **and delete** (amount, currency, merchant, category, date, note)
- **Mass rename** (find/replace merchant, note, line-item text) — `FEATURE_MASS_RENAME`
- Expense list + filter (mobile-first UI)
- Multi-currency: store original amount/currency + base-currency amount
- Natural-language spend Q&A via Ollama (`lenai`) — model must exist on host
- **MCP server** (add / list / query / delete spend tools) — same domain API as the UI
- Feature-flag registry for every module
- Docker image → GHCR → Portainer compose → Cloudflare tunnel path
- Health endpoints + structured logging

**Explicitly excluded (deferred; flags OFF until ready):**

- Receipt OCR / **camera** ingest — V1.1 (`FEATURE_RECEIPT_OCR`)
- **Mass upload / directory bootstrap** — V1.1 (`FEATURE_MASS_UPLOAD`)
- Google Vision provider — V1.1 optional (`FEATURE_OCR_GOOGLE_VISION`)
- Bank statement CSV/PDF import — V1.1 (`FEATURE_BANK_IMPORT`)
- Email ingest — V1.2 (`FEATURE_EMAIL_INGEST`)
- Pattern / savings recommendations — V1.2 (`FEATURE_SAVINGS_INSIGHTS`)
- Historical charts / geospatial — V2 (`FEATURE_TRENDS_UI`, `FEATURE_GEO`)
- Line-itemization per receipt (“crisps” SKU-level) — V1.2
  (`FEATURE_LINE_ITEMS`) — V1 Q&A works on merchant/category/note text first

## Success Criteria (KPIs)

1. From a phone browser: add an expense in &lt; 30 seconds; see it in the list.
2. Ask “how much did I spend on groceries this month?” and get a correct total
   from Ollama + DB tools (not hallucinated invent).
3. From Cursor with MCP connected: `query_spend` returns the same total as the UI.
4. `docker compose` locally and Portainer stack on `notcoolio` both serve
   `/health/live`.
5. Every non-core module is gated by a documented feature flag.

## Getting Started

Refer to [README.md](./README.md) for build and deployment instructions.
Lessons from classic XTA live in `C:\projects\xta` (do not mutate that tree
from this repo).
