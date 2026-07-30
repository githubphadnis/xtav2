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

## Spend date (critical)

`spent_on` must be the **printed receipt date**, never the upload/OCR day.

Resolution order (`app/services/receipts.py`):

1. Deterministic parse of Google OCR text (`Datum` / `Date` / header `DD.MM.YY`)
2. LLM `spent_on` if valid
3. Last resort: today + note `date:unparsed` (Pending warns — fix before confirm)

Existing rows already stored with upload dates stay wrong until edited or re-scanned
(or wiped + reimported — see below).

## Reset + reimport (fix wrong dates, #24)

Keeps the **uploads volume**; deletes **all expense rows** (manual + bank + receipt).
Bank CSV must be re-imported afterward if you use it.

1. Deploy image that includes `app.tools.reimport_receipts`.
2. Confirm Google Vision effective (Settings) so OCR quality matches Capture.
3. Dry-run inside the app container:

```bash
python -m app.tools.reimport_receipts --dry-run
```

4. Wipe + re-OCR (destructive — requires `--yes`):

```bash
python -m app.tools.reimport_receipts --wipe --ocr --yes
```

Or from the LAN (host `:4280`), after Pull/redeploy:

```bash
curl -sS -X POST http://<notcoolio>:4280/ops/reimport \
  -H "Content-Type: application/json" \
  -d '{"confirm":"WIPE_AND_REIMPORT","dry_run":true}'

curl -sS -X POST http://<notcoolio>:4280/ops/reimport \
  -H "Content-Type: application/json" \
  -d '{"confirm":"WIPE_AND_REIMPORT","wipe":true,"ocr":true}'
```

If `OPS_REIMPORT_TOKEN` is set in Portainer, also send `Authorization: Bearer <token>`.
Without a token, only private LAN clients may call (same trust as the open LAN UI).

5. Open **Pending** — check each `spent_on` against the printed `Datum`, then confirm.
6. Re-import bank CSV if needed (`/bank`).

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
- **UI:** Pending and Expenses warn; **Not a duplicate** dismisses the flag.
- **Rescan:** on app startup for recent rows (catch-up after deploy).

Empty merchant with no line items → no fingerprint (avoids false matches).

