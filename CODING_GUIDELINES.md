# Coding Guidelines

Language- and style-level rules for **cOcO** ("co-coded") projects. These are the
*mechanics* of writing code. Process, governance, and documentation lifecycle live
in [`agent_rules.md`](./agent_rules.md); the portable entrypoint that ties both
together is [`AGENTS.md`](./AGENTS.md).

> Scope: applies to any agent or human writing code in a cOcO project, regardless
> of the tool (Cursor, openCode, Claude Code, Copilot, plain editor).

## Universal

- **No hardcoding.** Endpoints, timeouts, ports, paths, and secrets come from config
  or environment variables — never literals in code.
- **Never commit secrets.** No credentials, tokens, or API keys in source. Read from
  env vars or a secret store. Keep secret files out of git via `.gitignore`.
- **Comment "why", not "what".** Document intent, trade-offs, and workarounds — not
  obvious mechanics.
- **Public APIs are documented.** Every public function, class, and method has a
  docstring (Python docstring, JSDoc, GoDoc, etc.) covering params, returns, and behavior.
- **Fail loud, log with context.** Don't swallow errors; catch, log with context, and
  fail gracefully.
- **No naked `print` / `console.log`** for core logic — use the language's logging
  framework with configurable levels.

## Python

- Type hints on all function signatures.
- Max line length: 100 characters.
- Use `pathlib` for filesystem paths (not `os.path` string juggling).
- Format with a standard formatter (e.g. `black`/`ruff format`) and lint (`ruff`/`flake8`).

## JavaScript / TypeScript

- Prefer TypeScript; type all exported functions.
- Format with Prettier; lint with ESLint.
- Use `const`/`let` (never `var`); prefer async/await over raw promise chains.

## Go

- `gofmt`/`goimports` clean; `go vet` clean.
- Wrap errors with context (`fmt.Errorf("...: %w", err)`).

## Git

- **Commit messages:** Conventional Commits — `type(scope): short description`
  (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`). Reference issue numbers
  where applicable (e.g. `fix(auth): handle empty token (#42)`).
- **Branch names:** `feature/`, `fix/`, `chore/`, `docs/` prefixes.
- Keep commits small and focused; one logical change per commit.

## Documentation

- Keep `README.md` aligned with architecture changes (see `agent_rules.md` for the
  full documentation lifecycle: `dev-docs.md`, `handover.md`, `BREADCRUMBS.md`).
