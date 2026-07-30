# Changelog

All notable changes to xtav2 are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Nav and Insights buttons: **Ledger** → **Expenses**; brand sub “expense tracker”.

### Fixed
- Insights rolling 3-month chart: use `rem` bar heights (CSS `%` collapsed → invisible).
- Ask: “top 5 most expensive items this month” now returns ranked line items
  (deterministic; respects this-month window) instead of a generic LLM reply.
- Receipt **`spent_on`** no longer silently uses upload day: OCR text `Datum`/header
  date wins over LLM; unknown dates get `date:unparsed` + Pending warning ([#24](https://github.com/githubphadnis/xtav2/issues/24)).

### Added
- Operator CLI `python -m app.tools.reimport_receipts --wipe --ocr --yes` to wipe
  expenses and re-OCR files in `UPLOAD_DIR` ([#24](https://github.com/githubphadnis/xtav2/issues/24)).
- Insights visuals: MoM/rolling 3-mo chart with amount peaks, hero key message,
  ranked category/merchant cards; Expenses / Ask as buttons; no list index bullets.
- **Insights Phase 1** ([#20](https://github.com/githubphadnis/xtav2/issues/20), `FEATURE_TRENDS_UI`):
  `/insights` MoM pulse, category + merchant bars; tap → ledger filter or Ask preload.
- **Bank CSV import + reconcile** ([#17](https://github.com/githubphadnis/xtav2/issues/17), `FEATURE_BANK_IMPORT`):
  `/bank` upload; link bank↔receipt on one row; enrich line items on confirm; Ask counts once.
- Insights design `docs/insights.md`; later phases: geo [#21], line-item cats [#22], cloud LLM [#23].
- Multi-screen mobile UI (Ledger / Add / Capture / Pending / Ask / Settings) with bottom nav.
- Privacy toggle (`PRIVACY_LOCAL_ONLY` + Settings UI) — blocks Google Vision when on.
- Optional Google Vision OCR path (`FEATURE_OCR_GOOGLE_VISION` + `GOOGLE_VISION_API_KEY`).
- **Line items** (`FEATURE_LINE_ITEMS`): `expense_line_items` + Ask `line_total` / product questions.
- Google-first OCR pipeline (local vision = privacy fallback only).
- Async Capture OCR: upload → `processing` spool → Pending when done (no UI jam).
- Duplicate detection (`duplicate_of_id`): flag same date/amount/merchant; exclude from Ask until dismissed.
- Tool-calling Ask agent + product synonyms (kebab↔Döner, etc.).
- **Multi-currency FX:** ECB/Frankfurter rates → `amount_base`; ledger ≈ base; `/health/fx`.
- Professional mobile chrome: Fraunces + Source Sans 3, teal/paper palette (no muddy green gradient).
- OCR post-processing: reject junk categories, absurd dates; tighter German-receipt vision prompt.
- cOcO Rule 15 (Production-Path Parity) and Rule 16 (Rule Promotion) synced from scaffolding.
- Expense delete in UI + MCP (`delete_expense`); default Ollama model `qwen2.5:14b`.
- Feature flag `FEATURE_MASS_UPLOAD` (off) for directory/multi-file bootstrap.
- Docker Publish **smoke** job: run image + Postgres, hit `/health/live|db|flags|ollama`.
- Receipt **camera capture** (`FEATURE_RECEIPT_OCR`): pending queue + confirm; optional Ollama vision.

- Initial cOcO Governed scaffold and XTAv2 V1 skeleton.
- Manual expense entry (mobile-first UI) behind `FEATURE_MANUAL_ENTRY`.
- Multi-currency fields + base currency config (`FEATURE_MULTI_CURRENCY`).
- Ollama Q&A path (`FEATURE_OLLAMA_QA`) using aggregate + LLM wording.
- MCP server module (`FEATURE_MCP`) with add/list/query/flag tools.
- Feature-flag registry for OCR, bank, email, insights (default off).
- Docker Compose (local) + Portainer compose + CI / GHCR publish workflows.
