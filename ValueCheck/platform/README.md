# Equity research platform — backend

Local-first, production-grade equity research: deterministic DCF valuations from
real SEC filings + market data, with an auditable source trail. Hexagonal
architecture, strictly typed, phase-by-phase build (see `../BUILD_SPEC.md` and
`../CLAUDE.md`).

## Layout

```
src/equity/
  config.py        # pydantic-settings, env-driven
  logging.py       # structlog setup
  errors.py        # typed exceptions + stable error codes
  domain/          # PURE. DCF math + models. No I/O. (Phase 1)
  ports/           # interfaces (Protocol/ABC)          (Phase 2+)
  adapters/        # implement ports; all I/O           (Phase 2+)
  application/     # use-cases + composition root       (Phase 4+)
  api/             # FastAPI; thin                       (Phase 0: /health)
tests/{unit,contract,integration,api}/
scripts/           # export_openapi.py, (later) seed_demo, live_smoke
```

Dependencies flow inward only: `api → application → adapters → ports → domain`.
`domain` imports nothing outward and does zero I/O. This is enforced in CI by
`import-linter` (`.importlinter`).

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for env + dependency management

## Getting started

```bash
uv sync --extra dev      # or: make install
make run                 # serves http://127.0.0.1:8000/health
```

## Quality gate

Every change must pass the full gate before a PR:

```bash
make gate                # = lint + typecheck (mypy --strict + import-linter) + test
```

Individual targets: `make lint`, `make typecheck`, `make contracts`, `make test`,
`make cov`, `make openapi`. Run `make help` for the full list.

## Configuration

All settings are env-driven with the `EQUITY_` prefix; see `.env.example`.
Copy it to `.env` for local overrides. Never commit `.env` or secrets.
