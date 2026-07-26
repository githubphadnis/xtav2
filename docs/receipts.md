# Receipt camera capture

## Flags

| Flag / setting | Default | Role |
|----------------|---------|------|
| `FEATURE_RECEIPT_OCR` | `false` | Show Capture / Pending screens |
| `FEATURE_OCR_OLLAMA_VISION` | `false` | Auto-extract via Ollama vision on lenai |
| `FEATURE_OCR_GOOGLE_VISION` | `false` | Cloud OCR via Google Vision API |
| `PRIVACY_LOCAL_ONLY` | `true` | Bootstrap: block cloud OCR (Settings UI can override) |
| `GOOGLE_VISION_API_KEY` | empty | Required for Google path |
| `OLLAMA_VISION_MODEL` | empty | e.g. `minicpm-v` / `qwen2.5vl` on lenai |

## OCR routing

1. If local vision is enabled and the model exists → Ollama vision.
2. Else if privacy is **off**, Google flag is on, and API key is set → Google OCR text, then local chat model structures fields.
3. Else → pending draft with empty/manual fields.

**Privacy local-only** (Settings screen or env) always blocks Google, even when the feature flag is on.

## Flow

1. **Capture** screen: camera via `<input accept="image/*" capture="environment">`.
2. Upload stores the image under `UPLOAD_DIR` and creates `status=pending`.
3. **Pending** screen: confirm → `status=posted` (counts toward Ask totals).

## Model quality (practical)

| Provider | Receipt field accuracy (rough) | Notes |
|----------|--------------------------------|-------|
| LLaVA-class local | Often weak | Hallucinates totals / merchants |
| MiniCPM-V / Qwen2.5-VL | Much better | Prefer these for local OCR |
| Google Vision + local structure | Strongest cloud option | ~90%+ on clean receipts; sends image off-host |

Default stance: **local-first**. Enable Google only when privacy is off and you accept cloud OCR.

## Portainer

```text
FEATURE_RECEIPT_OCR=true
FEATURE_OCR_OLLAMA_VISION=false
OLLAMA_VISION_MODEL=              # pull minicpm-v or qwen2.5vl on lenai first
PRIVACY_LOCAL_ONLY=true
FEATURE_OCR_GOOGLE_VISION=false
GOOGLE_VISION_API_KEY=            # never commit; set in Portainer secrets/env
UPLOAD_DIR=/data/uploads
```

Compose mounts volume `xtav2_uploads` → `/data/uploads`.

## Note on lenai (Jul 2026)

Current inventory has chat/coder/embed models but **no vision model**. Camera capture
still works: drafts land in pending for manual confirm. Pull a vision model before
turning `FEATURE_OCR_OLLAMA_VISION` on.
