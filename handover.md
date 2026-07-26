# Handover — xtav2

## Last Worked On Date

2026-07-26

## Current State / WIP

- **Live:** https://xta.pphadnis.com/
- Line items + Google-primary OCR on `main` — pull image + set Portainer env
- Next product: mass upload (#9)

## Broken Things

- Ask matches printed product text (e.g. German `Schokolade`), not English synonyms yet

## Next Immediate Steps

1. Portainer env (see docs/receipts.md):
   - `FEATURE_OCR_GOOGLE_VISION=true`
   - `GOOGLE_VISION_API_KEY=<from wdmmgv2 GCLOUD_VISION_API_KEY>`
   - `PRIVACY_LOCAL_ONLY=false`
   - `FEATURE_LINE_ITEMS=true`
2. Settings: privacy off; Google Vision effective = yes
3. Recapture receipt → confirm line items → Ask product question
4. Start #9 mass upload
