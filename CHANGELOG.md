# Changelog

All notable changes to xtav2 are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- cOcO Rule 15 (Production-Path Parity) and Rule 16 (Rule Promotion) synced from scaffolding.
- Expense delete in UI + MCP (`delete_expense`); default Ollama model `qwen2.5:14b`.
- Feature flag `FEATURE_MASS_UPLOAD` (off) for directory/multi-file bootstrap.
- Docker Publish **smoke** job: run image + Postgres, hit `/health/live|db|flags|ollama`.

- Initial cOcO Governed scaffold and XTAv2 V1 skeleton.
- Manual expense entry (mobile-first UI) behind `FEATURE_MANUAL_ENTRY`.
- Multi-currency fields + base currency config (`FEATURE_MULTI_CURRENCY`).
- Ollama Q&A path (`FEATURE_OLLAMA_QA`) using aggregate + LLM wording.
- MCP server module (`FEATURE_MCP`) with add/list/query/flag tools.
- Feature-flag registry for OCR, bank, email, insights (default off).
- Docker Compose (local) + Portainer compose + CI / GHCR publish workflows.
