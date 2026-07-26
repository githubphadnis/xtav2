# Security, hardening & compliance backlog

**Status:** deferred — collect here; execute in a dedicated iteration (not mixed into OCR/line-item delivery).

**Tracking issue:** open/link GitHub issue “Security & compliance hardening”.

---

## Secrets & Google Vision

- [ ] Send Vision API key via `x-goog-api-key` header (not `?key=` query string) to reduce proxy/access-log leakage
- [ ] Prefer **service account** (JWT / ADC) over long-lived API keys for Vision in production
- [ ] GCP key restrictions: Vision API only; IP allowlist for notcoolio egress if stable
- [ ] Portainer/Docker **secrets** (not plain stack env) for `GOOGLE_VISION_API_KEY` / DB passwords
- [ ] Confirm keys never appear in app logs, health payloads, or error pages
- [ ] Rotate key used from wdmmgv2 lineage; document ownership in GCP project

## Auth & access

- [ ] Cloudflare Access (or equivalent) in front of `xta.pphadnis.com` before wider sharing
- [ ] App-level auth if Access is insufficient (session / OIDC)
- [ ] Separate read-only vs operator roles (later)

## Privacy & data

- [ ] Document data flows: receipt images → Google Vision when privacy off; local-only path
- [ ] Retention policy for uploads volume (`xtav2_uploads`) and pending drafts
- [ ] Explicit consent / settings copy when enabling cloud OCR
- [ ] Option to purge receipt images after confirm (keep line items only)
- [ ] GDPR-oriented export/delete of personal spend data

## Transport & headers

- [ ] Enforce HTTPS-only (Cloudflare); HSTS
- [ ] Security headers (CSP, X-Frame-Options, Referrer-Policy, etc.)
- [ ] Do not expose internal hostnames (`lenai`) in client-visible errors

## Dependency & supply chain

- [ ] Pin/base-image updates; Dependabot or equivalent
- [ ] Scan GHCR images (Trivy/Grype in CI)
- [ ] No secrets in git history; `.env` audit

## Compliance / ops notes (future)

- [ ] Threat model one-pager (assets: receipts, spend, API keys, Ollama)
- [ ] Incident response: key rotation checklist
- [ ] Public-launch checklist before marketing xtav2 externally

---

## Explicitly out of this backlog file

Product features (mass upload, nutrition, rebates, PWA) stay on the product roadmap — link only if they create new security surface.
