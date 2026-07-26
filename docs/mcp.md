# MCP server

When `FEATURE_MCP=true`, xtav2 exposes an MCP server so Cursor (and other
agents) can use the **same domain services** as the web UI.

## Tools (V1)

| Tool | Purpose |
|------|---------|
| `add_expense` | Create a manual expense |
| `delete_expense` | Delete an expense by id |
| `list_expenses` | List / filter recent expenses |
| `query_spend` | Aggregate spend for a natural or structured query window |
| `list_feature_flags` | Show which modules are enabled |

## Run (dev)

```bash
# after app deps installed and DB up
python -m mcp_server
```

Configure Cursor MCP to launch that module (stdio). Prefer env from `.env`
(`DATABASE_URL`, `OLLAMA_*`, `FEATURE_*`).

## Design rules

- MCP is a **transport**, not a second business layer.
- Tools call `app.services.*` only.
- Tools for flagged-off modules must not appear in the tool list.
