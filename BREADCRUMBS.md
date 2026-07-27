# Breadcrumbs — xtav2

## Session: 2026-07-27 (CI fix)

- **Work done:** Fixed CI/Docker Publish — ruff 0.16 lint failures since FX/bank
  (`a639d03`). CI + Docker Publish green; image `ghcr.io/githubphadnis/xtav2:main` rebuilt.
- **Cause:** `ruff>=0.8` floated to 0.16 with new rules (DTZ/UP/FURB/I001).
- **Next:** Redeploy Portainer; enable `FEATURE_TRENDS_UI` / `FEATURE_BANK_IMPORT` as needed.
