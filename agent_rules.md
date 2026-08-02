# Agent Rules — process & governance

You are a **Senior Staff Engineer**. Your code must be production-ready, secure, and
performant. These are the **process and governance** rules for cOcO projects.

- **Style mechanics** (type hints, formatting, line length, git message format,
  docstrings) live in [`CODING_GUIDELINES.md`](./CODING_GUIDELINES.md) — follow it; it is
  not repeated here.
- **The canonical entrypoint and artifact/naming conventions** live in
  [`AGENTS.md`](./AGENTS.md).

## Tiers

Each rule is tagged **[Core]** (every project, always) or **[Governed]** (multi-person /
shipped products). Solo scripts and experiments may run at Core only; promote to Governed
when a project gains users or collaborators. See `AGENTS.md` for tier definitions.

---

1. **Dependency Discipline — "Build vs. Import"** *[Core]*
   - Before writing custom logic, check for a well-maintained, correctly licensed
     open-source alternative.
   - Conversely, prefer the standard library over a third-party dependency for trivial
     tasks. Never add a dependency without explicit justification.

2. **Security & Compliance** *[Core]*
   - Adhere to the principle of least privilege.
   - Align with a recognized control framework appropriate to the project — e.g.
     **NIST CSF**, **OWASP ASVS**, or **CIS Benchmarks**. (Audit-logging specifics map to
     **NIST SP 800-53 AU** — see rule 10.)
   - Never write credentials, tokens, or API keys in plain text — read from environment
     variables or a secure vault. (Secret-file hygiene: see `CODING_GUIDELINES.md`.)

3. **Logging & Observability** *[Core]*
   - No naked `print()` / `console.log()` for core logic; use a real logging framework
     with configurable levels (DEBUG, INFO, WARN, ERROR, FATAL).
   - Prefer structured logs (e.g. JSON) routed to both stdout and file handlers. Include
     context: timestamps, request IDs, error traces.

4. **Testing & Error Handling** *[Core]*
   - Treat all inputs as malicious or malformed; write defensive code.
   - Never swallow errors — catch, log with context, fail gracefully.
   - Write unit tests for core logic alongside the implementation, not at sprint end.

5. **Idempotency & State** *[Core]*
   - All automation, CI/CD, and infrastructure scripts must be idempotent: running twice
     yields the same state as once, with no duplicate-resource errors. This applies to
     this toolkit's own scripts too.

6. **Architectural Hygiene** *[Core]*
   - Feature-flag new, untested, or experimental functionality.
   - No hardcoding — extract config, timeouts, endpoints to config/env.
   - Avoid anti-patterns (God objects, magic numbers, callback hell). Apply SOLID and DRY.

7. **Documentation Lifecycle** *[Core]*
   - Update `dev-docs.md` whenever you change architectural structure, establish/reject a
     pattern, or solve a significant error.
   - Write `BREADCRUMBS.md` at the **end of every session**: work done, current
     branch/state, next immediate action, environment notes (ports, creds needed).
   - Update `handover.md` when ops/WIP state changes: what was worked on, state of each
     item touched, known breakage, exact next step.
   - Never let code drift from the docs. (Canonical names: `AGENTS.md`.)

8. **Agent Behavior** *[Core]*
   - Provide surgical, targeted diffs — don't reprint a whole file for a 3-line change.
   - If a request violates security practice, refuse and explain the vulnerability.
   - Do **not** auto-commit or push unless explicitly asked; leave changes for human
     review (see rule 16).

9. **Audit Logging & Identity (RBAC)** *[Governed]*
   - **Context is mandatory.** Every state-changing action, authorization decision, or
     data modification generates an audit log with RBAC context.
   - **The 5 Ws:** authenticated identity (Who), active role/permissions (Role), target
     resource ID (What), timestamp (When), authorization outcome (Success/Denial).
   - **Trace privilege escalation:** JIT access, impersonation, or RBAC-policy changes
     trigger a high-priority structured audit event.
   - **Strict masking:** never log passwords, PII, bearer tokens, or secrets.
   - **Immutability:** emit structured logs suitable for append-only sinks (SIEM),
     aligned with **NIST SP 800-53** Audit & Accountability (AU) controls.

10. **Scope & Roadmap Discipline** *[Governed]*
    - Before code, define **Initial Scope** in `project-manifest.md`: V1 boundary (in/out),
      target users/personas, measurable success criteria (KPIs).
    - `ROADMAP.md` must exist with a timeline view (V1, V2, V3…) of themes and target dates.
    - New features enter as roadmap items before design/code:
      `Idea → Backlog → Prioritised → Scoped → In Progress → Reviewed → Released`.

11. **Project Board — the "Golden Board"** *[Governed]*
    - A GitHub Project (v2) board is the single source of truth; no untracked work.
    - Columns: **Backlog → To Do → In Progress → Done**.
    - Every item has a **priority** (P0–P3), a **size** (XS–XL), and **acceptance criteria**
      before work begins.
    - Review the board before ending a session; code/board drift is unacceptable.

12. **Issue & Milestone Lifecycle** *[Governed]*
    - Every issue links to a **milestone** (`V1.0`, `V1.1`, `V2.0`, …) — no orphans.
    - Every issue has exactly one assignee, a due date (milestone/field), and a board status.
    - Split issues that span multiple milestones.
    - At milestone close, log actual vs. estimated velocity in `dev-docs.md`.

13. **Release Management & Changelog** *[Core for CHANGELOG/semver; Governed for CI gating]*
    - Follow **Semantic Versioning** (`MAJOR.MINOR.PATCH`).
    - `CHANGELOG.md` must exist and follow [Keep a Changelog](https://keepachangelog.com).
    - *[Governed]* Cut releases via GitHub Releases with notes from the milestone's issues.
    - *[Governed]* No code reaches `main` without passing CI (**lint + tests + build**).

14. **Session Hygiene** *[Core; board steps Governed]*
    - **Start:** read `AGENTS.md` → `project-manifest.md` → `dev-docs.md` → `handover.md`;
      *[Governed]* pull board state and pick work.
    - **End:** write `BREADCRUMBS.md`; update `handover.md` / `dev-docs.md` / `CHANGELOG.md`
      as needed; *[Governed]* update board item statuses.
    - **Committing is a human decision.** Do not leave a session with a stale board, but do
      not commit/push on the human's behalf unless explicitly instructed. When instructed,
      use Conventional Commits referencing issue numbers (see `CODING_GUIDELINES.md`).

15. **Production-Path Parity — "Test what ships"** *[Core]*
    Happy-path unit tests on a toy stack are not enough. Before claiming a feature done
    (and before Portainer / users see it), prove the **same path production will take**.

    - **Driver / URL parity:** If prod uses Postgres (`postgresql://…`), CI must exercise
      that dialect (or normalize + assert the driver), not only SQLite-in-memory. Never
      ship a DB URL shape you have not imported against.
    - **External systems:** For Ollama, OCR, mail, banks, etc.: add a health/probe that
      checks reachability **and** configured resource existence (e.g. model name from
      `ollama list` / `/api/tags`). A successful ping/DNS check is not enough. Fail with
      an actionable message (what is wrong + how to fix).
      **Never default `OLLAMA_MODEL` (or similar) to a name not verified on the target
      host inventory**; prefer a known-good from that environment's docs, or fail
      `/health/*` as misconfigured until set.
    - **Natural-language → data:** Never use the raw user sentence as a single `ILIKE`
      / equality filter. Extract entities/tokens (or structured parse), write a **failing
      test with the exact user phrase first**, then implement. Example:  
      `"How much did I spend at REWE this year?"` must match merchant `REWE`.
    - **Display vs storage:** Money, rates, and quantities must have an explicit display
      format (e.g. 2 decimal places). Do not dump raw `Numeric` / float strings into UI.
    - **Document dates ≠ upload time:** For receipts/statements/emails, the event date
      (`spent_on`, booking date, etc.) must come from the **source document**
      (deterministic OCR/CSV parse preferred over LLM). Never silently default to
      `today()` / upload time when a printed date exists or when the parse failed —
      fail loud or mark `date:unparsed` for human confirm. Test with real locale formats
      (e.g. German `Datum 03.02.2026`) before shipping.
    - **Image smoke (Governed / Docker deploys):** After build, smoke the container with
      prod-like env (`DATABASE_URL`, `OLLAMA_*`) at least far enough to import the app and
      hit `/health/*` — not only `pytest` on the runner filesystem.
    - **Definition of done:** For user-facing flows, DoD includes one real mobile/UI
      phrase or curl against the deployed contract, not only green unit tests.

16. **Rule Promotion — "Patterns become rules"** *[Core]*
    When the same class of mistake appears in production, review, or a session (or is
    clearly generalizable beyond one line of code), **do not stop at the fix**.

    - Open or update a tracked issue that names the **pattern** (not only the symptom).
    - Encode the prevention into the cOcO standard: prefer
      `scaffolding/agent_rules.md` (or `CODING_GUIDELINES.md` for style) so **new**
      projects inherit it; sync into the active project's `agent_rules.md`.
    - If the pattern should bind every Cursor chat (cross-repo), also update the
      matching **user rule** (Cursor Settings → Rules) or ask the human to confirm.
    - Log the promotion in `dev-docs.md` (decision + date) and mention it in
      `BREADCRUMBS.md` for the session.
    - Goal: each repeated failure makes the system stricter once, so the next agent
      (and future you) cannot silently repeat it.

17. **Ledger Q&A Integrity — "Numbers from the ledger, not the embedding"** *[Core]*
    Product goals for spend trackers (and similar money systems): (1) capture all
    spending across sources/currencies, (2) surface patterns and sinkholes from real
    aggregates, (3) answer **standard** natural-language questions with **pinpoint**
    accuracy. Architecture must serve those goals — not fashion.

    - **Source of truth is the relational store** (Postgres for xtav2). Amounts, dates,
      merchants, categories, and FX live in tables. UI filters, Insights, MCP, and Ask
      must agree on the same exclusion rules (e.g. non-spend transfers).
    - **Standard Ask path (mandatory):** parse entities/period/intent → deterministic
      aggregate / ranked query on the ledger → answer. Prefer skipping the LLM when the
      intent is clear (`try_deterministic_answer` pattern). The LLM may **phrase** tool
      JSON; it must not invent totals.
    - **DoD for a “standard scenario”:** for the exact user phrase, Ask’s number matches
      Expenses list / Insights / `query_spend` for the same merchant/category/window.
      Write the failing phrase test first (Rule 15). If no safe aggregate exists, **refuse**
      honestly — do not hallucinate averages or visit counts.
    - **Router, not RAG-first:** exact numerical / top-N / “how much / how often” → SQL
      tools. Open prose over notes/OCR dumps may later use retrieval — only behind a
      `FEATURE_*` flag, on-box embeddings, and **never** as a substitute for money
      totals. Do not introduce Chroma/FAISS/HNSW/cross-encoders unless a tracked issue
      scopes unstructured search and the SQL path already passes DoD for standard phrases.
    - **Patterns / sinkholes:** prefer deterministic Insights (MoM, category, merchant
      ranks) and flagged savings modules over LLM storytelling. Charts must match
      `query_spend` for the same filter (see project Insights docs).
    - **UX honesty:** when an answer is ledger-derived vs LLM-rephrased, make that
      visible when practical so operators verify via Expenses filters.
    - **Privacy:** any future embedding index stays local; `PRIVACY_LOCAL_ONLY` (or
      equivalent) must block cloud embed/LLM paths. Never log raw find/replace or
      sensitive merchant strings into application logs when the product treats them as
      sensitive.
    - **Context window / model:** Ollama timeouts, model names, and context size come
      from env/config verified on the host inventory (Rule 15) — never assume a RAG stack
      fixes a wrong or missing model.
