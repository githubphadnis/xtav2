# Feature flags

Every module is gated by an environment variable. Flags are booleans parsed from
`true`/`1`/`yes` (case-insensitive). Snapshot: `GET /health/flags`.

| Flag | Default (V1) | Module |
|------|--------------|--------|
| `FEATURE_MANUAL_ENTRY` | `true` | Manual expense form + API |
| `FEATURE_MULTI_CURRENCY` | `true` | Original + base currency amounts |
| `FEATURE_OLLAMA_QA` | `true` | Natural-language spend questions |
| `FEATURE_MCP` | `true` | MCP server process / tools |
| `FEATURE_RECEIPT_OCR` | `false` | Receipt photo / camera ingest + pending queue |
| `FEATURE_MASS_UPLOAD` | `false` | Bulk ingest from a directory / multi-file upload |
| `FEATURE_OCR_OLLAMA_VISION` | `false` | Ollama vision OCR provider (needs `OLLAMA_VISION_MODEL`) |
| `FEATURE_OCR_GOOGLE_VISION` | `false` | Google Vision OCR (blocked when privacy local-only) |
| `PRIVACY_LOCAL_ONLY` | `true` | Bootstrap privacy; Settings UI can override at runtime |
| `FEATURE_BANK_IMPORT` | `false` | CSV/Excel/PDF bank statements |
| `FEATURE_EMAIL_INGEST` | `false` | Email → expense pipeline |
| `FEATURE_LINE_ITEMS` | `false` | Per-SKU line items on receipts |
| `FEATURE_SAVINGS_INSIGHTS` | `false` | Pattern / savings suggestions |
| `FEATURE_TRENDS_UI` | `false` | Historical charts |
| `FEATURE_GEO` | `false` | Geospatial spend map |

Disabled modules must not register routes, MCP tools, or background jobs.
