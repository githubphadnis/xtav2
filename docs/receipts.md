# Receipt camera capture

## Flags

| Flag | Default | Role |
|------|---------|------|
| `FEATURE_RECEIPT_OCR` | `false` | Show camera/file upload + pending queue |
| `FEATURE_OCR_OLLAMA_VISION` | `false` | Auto-extract fields via Ollama vision |
| `FEATURE_OCR_GOOGLE_VISION` | `false` | Reserved (not implemented) |

## Flow

1. Mobile opens camera via `<input accept="image/*" capture="environment">` (gallery also works).
2. Upload stores the image under `UPLOAD_DIR` and creates an expense with `status=pending`.
3. If vision OCR is enabled **and** `OLLAMA_VISION_MODEL` exists on lenai, fields are pre-filled.
4. Operator confirms in **Pending receipts** → `status=posted` (counts toward Ask totals).

## Portainer

```text
FEATURE_RECEIPT_OCR=true
FEATURE_OCR_OLLAMA_VISION=false   # keep false until a vision model is pulled on lenai
OLLAMA_VISION_MODEL=              # e.g. llava or minicpm-v when available
UPLOAD_DIR=/data/uploads
```

Compose mounts volume `xtav2_uploads` → `/data/uploads`.

## Note on lenai (Jul 2026)

Current inventory has chat/coder/embed models but **no vision model**. Camera capture
still works: drafts land in pending for manual confirm. Pull a vision model before
turning `FEATURE_OCR_OLLAMA_VISION` on.
