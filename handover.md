# Handover — xtav2

## Last Worked On Date

2026-07-26

## Current State / WIP

- **Live:** https://xta.pphadnis.com/
- Multi-screen UI + privacy toggle + optional Google Vision on `main` (pull image)
- Camera: `FEATURE_RECEIPT_OCR=true`; vision OCR still optional
- Next product: mass upload (#9)

## Broken Things

- None known for core ledger/Ask
- Auto OCR needs a vision model on lenai (`OLLAMA_VISION_MODEL` + flag) **or**
  privacy off + Google Vision key

## Next Immediate Steps

1. Portainer: pull latest image; keep `PRIVACY_LOCAL_ONLY=true` unless you want cloud OCR
2. Phone test: Ledger / Add / Capture / Pending / Ask / Settings
3. Optional: pull `minicpm-v` or `qwen2.5vl` on lenai for local OCR
4. Start #9 mass upload
