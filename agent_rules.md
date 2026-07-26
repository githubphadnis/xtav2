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
