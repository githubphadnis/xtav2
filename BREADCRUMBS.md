# Breadcrumbs — xtav2

## Session: 2026-08-02 (Ask clarify + Insights windows)

- Ask: word-boundary for line match (`tom` ≠ tomato); ≥2 distinct labels → choose-one
  buttons on `/ask`. Tests for Tom vs RISPENTOMATE + Tom Hardy vs Tom Ford.
- Insights #29: shops = last **3** months; line items = last **6** months.
- 56 tests green. Push for Portainer next.

## Session: 2026-08-02 (Insights #29 + Ask TOM Q)

- Insights: top 5 shops by visits + top 10 line items w/ avg (#29).
- Ask Q: `How much on TOM` → ILIKE `%tom%` matches `Tom Hardy` (and Tomato risk) —
  addressed by word-boundary + clarify above.
- Prior: Ask line-SKU fix pushed `3a9c616`.

## Session: 2026-08-02 (Ask line-SKU miss — not RAG)

- User: Mass rename finds Kevin on EDEKA lines; Ask “on Kevin” / “Tom Hardy” → 0.00.
- Root cause: `on X` parsed as **merchant** (header only); line items ignored; multi-word
  truncated to first token. **Not a RAG gap** — data was in Postgres.
- Fix: multi-word entity parse; merchant Ask also searches line descriptions; prefer
  line totals when header count is 0. Test: `test_ask_line_item_after_mass_rename_not_merchant`.
- Pushed `3a9c616`.

## Session: 2026-08-02 (Ask integrity / cOcO Rule 17)

- Promoted Ask architecture into **Rule 17** (`agent_rules.md`): numbers from ledger,
  not embeddings; RAG only as optional flagged unstructured search.
- Added `.cursor/rules/ask-integrity.mdc`; updated `docs/ask.md` Future priority order.
- Rewrote mega RAG system-prompt into lean product-aligned prompt (see chat).
- Next Ask work: deterministic intents + “from ledger” UI — **not** Chroma/FAISS.

## Session end: 2026-08-02 (mass rename #28)

- Opened [#28](https://github.com/githubphadnis/xtav2/issues/28) (V1.0); roadmap/manifest/flags updated.
- Implemented find/replace: `app/services/mass_rename.py`, `/rename` UI, Settings link,
  MCP `mass_rename` (`dry_run` default). Fields: merchant, note, line items.
- Tests: `tests/test_mass_rename.py` (8); full suite **52 passed**.
- Pushed `3e71123`; Portainer deploy — Mass rename confirmed working by human.
- Env: `FEATURE_MASS_RENAME=true` (default).

## Session end: 2026-08-01 (restart)

- Added `docs/ask.md` (honest: Ask often shit; ledger-first; verify via Expenses).
- Wired into README / handover / ROADMAP / CHANGELOG.
- **Stop:** human restart. Next agent: read `handover.md` + `docs/ask.md`.
- Image target: `main` ≥ `166ed2d` (Ask fixes); docs commit after.

## Session: 2026-08-01 (docs sync)

- Confirmed docs lag: handover still described 108 Pending; Ask trust fixes not in CHANGELOG.
- Synced handover / breadcrumbs / changelog to prod + Ask state.

## Session: 2026-07-30 (Ask trust + CI)

- Ask: `on Google` merchant; stop `%am%` line noise; `\b` before at/on (Wh**at was**);
  calendar year `in 2025`; honest refuse for average/month; product vs merchant for Schokolade.
- CI red then fixed (`166ed2d`); Docker Publish green.
- Verify Google via Expenses filter — Ask 2764€/116 visits was false (~435€ / 16 rows).

## Session: 2026-07-30 (afternoon status)

- Non-spend transfers #27; bulk UX → #25/#26; bank = CSV `/bank` not Capture/PDF.
- Pending cleared by user; bank re-imported.

## Session: 2026-07-30 (ship Expenses + prod #24 wipe)

- Expenses rename + reimport; LAN `/ops/reimport`; 108 OCR → pending then confirmed.

## Session: 2026-07-29 (personal planning → daily_schedule)

- Personal schedule moved to `C:\projects\daily_schedule`; xtav2 product-only.

## Session end: 2026-07-27

- Insights rem bars; receipt date #24; bank #17; Ask top-N.
