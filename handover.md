# Handover — xtav2

## Last Worked On Date

2026-07-26

## Current State / WIP

- **Live:** https://xta.pphadnis.com/ (Cloudflare tunnel + Portainer on notcoolio)
- Ollama model configured on Portainer; Ask + manual CRUD + delete in use
- Next: CI image smoke (#6), then camera (#8) / mass upload (#9)

## Broken Things

- CI image smoke not yet on `main` until this session's push lands
- Camera / mass upload still flagged off

## Next Immediate Steps

1. Land Docker Publish `smoke` job (#6) and confirm Actions green
2. Start `#8` camera capture behind `FEATURE_RECEIPT_OCR`
3. Then `#9` mass upload behind `FEATURE_MASS_UPLOAD`
