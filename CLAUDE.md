# CLAUDE.md — Equity Research Platform

You are building a local-first, production-grade equity research platform. This
file is your standing brief; obey it across all sessions. Read `BUILD_SPEC.md`
in this repo for the full architecture and phase-by-phase acceptance criteria.

## What this is
A tool to run deterministic DCF valuations from real filings + market data,
attach research notes and tags, and (later) explore everything as a filterable
graph. A validated prototype core already exists (see "Seed code" below) — much
of Phase 1 is lifting that proven code into the target structure, not writing
DCF math from scratch.

## Prime directives (do not violate)
1. **Hexagonal boundaries are law.** `domain/` imports nothing outward.
   `application/` imports `domain` + `ports` only. `adapters/` implement `ports`.
   `api/` imports `application`. Nothing imports `api`. An `import-linter`
   contract enforces this in CI — if you need to cross a boundary, you're
   modeling it wrong; stop and reconsider, don't add the import.
2. **The domain is pure.** `domain/` does ZERO I/O — no network, no disk, no
   env reads, no logging side effects. DCF math stays framework-free
   (numpy/pandas only). If a domain function needs external data, it takes it
   as an argument.
3. **Don't reinvent the validated core.** The DCF engine, financial data model,
   and market adapter are already written and tested. Port them; don't rewrite
   their logic. Improve structure/types/tests, preserve behavior.
4. **Every external datum carries a source link.** Filings and market data both
   append a `SourceLink`. Never drop the audit trail.
5. **Typed, strictly.** `mypy --strict` must pass on backend. No `Any` escapes
   without a written reason. Pydantic for all API DTOs and settings.
6. **Config over hardcoding.** No hardcoded paths, URLs, keys, or magic numbers.
   Everything through `config.py` (pydantic-settings, env-driven).
7. **Lean.** Do not add a dependency without justifying it in the PR description
   against the approved list in `BUILD_SPEC.md`. Explicitly forbidden in v1:
   Celery, Redis, a task queue, an ORM (use raw SQL behind repository ports),
   Redux, GraphQL, any auth framework.

## Workflow rules
- **Work in phases.** Build strictly in the order in `BUILD_SPEC.md` §"Build
  order". Do not start a phase until the previous phase's acceptance criteria
  pass. One phase ≈ one PR.
- **Test-first for the domain.** Write/port the unit tests for DCF math before
  or alongside the code. Domain tests must run with no network.
- **Prove adapters against reality, but keep CI offline.** Network-touching
  adapters (Edgar, yfinance) get: (a) contract tests using mocks that run in
  CI, and (b) a separate, clearly-marked live-smoke script you run manually.
  Never make CI depend on sec.gov or Yahoo being up.
- **After each phase**, run the full gate: `make lint typecheck test`. All green
  before you open the PR. Report what you did, what you deferred, and why.
- **Ask before deviating.** If the spec is ambiguous or you believe a different
  approach is better, stop and surface it with a short recommendation rather
  than silently diverging. Small mechanical judgment calls you can make; anything
  affecting the architecture, dependencies, or the API contract you flag first.
- **Commit hygiene.** Small, focused commits. Conventional-commit messages.
  Never commit secrets, `.env`, or generated artifacts that belong in
  `.gitignore`.

## Environment expectations
- Python 3.12+, managed with the tooling already in the repo. Node 20+ for the
  frontend (Phase 6+).
- Network *is* available to you (unlike the environment the seed code was
  prototyped in). You SHOULD run live smoke tests against SEC EDGAR and Yahoo
  once the relevant adapters exist — the prototype could not, so you are the
  first place the live paths get exercised. Set `edgar.set_identity(...)` from
  an env var; never hardcode an email.
- Respect SEC fair-access norms: identity header required, throttle requests.

## Definition of done for any unit of work
- Types pass (`mypy --strict`, `tsc --noEmit` where relevant).
- Lint passes (`ruff`).
- Tests pass and meaningfully cover the new logic (not just happy path).
- Boundaries pass (`import-linter`).
- No new dependency without justification.
- Source links preserved. Config not hardcoded. Domain still pure.

## Seed code
The validated prototype lives at `/seed/` in this repo (or is pasted in the
kickoff message): `engine.py` (DCF), `data.py` (financials model + Edgar/
synthetic sources), `market.py` (market adapter). Treat these as the source of
truth for *behavior*. Phase 1 maps them onto the target package layout.

When in doubt: smaller, purer, better-tested, better-typed. Ship the phase, not
the whole thing.
