# Receipt capture + OCR + line items

## Recommendation

OCR is not a product goal. Prefer **Google Vision** for raw text, then local
Ollama (`OLLAMA_MODEL`) to structure header + `items[]`. Local vision
(`minicpm-v`) is a privacy-only fallback.

## Flags / settings

| Flag / setting | Default | Role |
|----------------|---------|------|
| `FEATURE_RECEIPT_OCR` | `false` | Capture / Pending screens |
| `FEATURE_LINE_ITEMS` | `true` | Store product lines; Ask can sum them |
| `FEATURE_OCR_GOOGLE_VISION` | `false` | Google DOCUMENT_TEXT_DETECTION |
| `GOOGLE_VISION_API_KEY` | empty | API key (Portainer; never commit) |
| `PRIVACY_LOCAL_ONLY` | `true` | Blocks Google when on (Settings can override) |
| `FEATURE_OCR_OLLAMA_VISION` | `false` | Local vision fallback |
| `OLLAMA_VISION_MODEL` | empty | e.g. `minicpm-v` |

## Pipeline

1. If privacy is off and Google flag + key are set → Google text → Ollama structure (with `items[]`).
2. Else if local vision enabled → Ollama vision (weaker line items).
3. Else → manual Pending fields.

## Portainer (good line-item quality)

```text
FEATURE_RECEIPT_OCR=true
FEATURE_LINE_ITEMS=true
FEATURE_OCR_GOOGLE_VISION=true
GOOGLE_VISION_API_KEY=<from wdmmgv2 / GCP>
PRIVACY_LOCAL_ONLY=false
FEATURE_OCR_OLLAMA_VISION=false
UPLOAD_DIR=/data/uploads
```

Then in the app **Settings**: confirm privacy local-only is **off** and
“Google Vision effective” is **yes**.

# Duplicate detection

On create/update of pending/posted expenses, xtav2 computes a fingerprint from
``spent_on + amount + normalized merchant`` (+ line-item hash when items exist).
A newer matching row is linked via ``duplicate_of_id`` (not auto-deleted).

- **Ask / totals:** active duplicates (linked and not dismissed) are excluded.
- **UI:** Pending and Ledger warn; **Not a duplicate** dismisses the flag.
- **Rescan:** on app startup for recent rows (catch-up after deploy).

Empty merchant with no line items → no fingerprint (avoids false matches).

