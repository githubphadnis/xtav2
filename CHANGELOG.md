# Changelog

All notable changes to xtav2 are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Initial cOcO Governed scaffold and XTAv2 V1 skeleton.
- Manual expense entry (mobile-first UI) behind `FEATURE_MANUAL_ENTRY`.
- Multi-currency fields + base currency config (`FEATURE_MULTI_CURRENCY`).
- Ollama Q&A path (`FEATURE_OLLAMA_QA`) using aggregate + LLM wording.
- MCP server module (`FEATURE_MCP`) with add/list/query/flag tools.
- Feature-flag registry for OCR, bank, email, insights (default off).
- Docker Compose (local) + Portainer compose + CI / GHCR publish workflows.
