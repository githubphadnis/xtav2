# Handover — xtav2

## Last Worked On Date

2026-07-26

## Current State / WIP

- **Live:** https://xta.pphadnis.com/
- Camera capture (#8) code on `main` — enable with `FEATURE_RECEIPT_OCR=true`
- Vision OCR off by default (no vision model on lenai yet)
- Next product: mass upload (#9)

## Broken Things

- None known for core ledger/Ask
- Auto OCR will fail until `OLLAMA_VISION_MODEL` is pulled + flag on

## Next Immediate Steps

1. Portainer: `FEATURE_RECEIPT_OCR=true`, pull latest image, ensure uploads volume
2. Phone test: camera → pending → confirm
3. Start #9 mass upload
