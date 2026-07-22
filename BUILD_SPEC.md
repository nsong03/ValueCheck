# BUILD_SPEC.md — Equity Research Platform

Executable architecture for the agent building this repo. Read alongside
`CLAUDE.md` (the standing rules). This document is the *what* and *in what
order*; `CLAUDE.md` is the *how you must behave*.

Locked scope for v1:
- Local-first, single user — built to deploy, no local-only shortcuts.
- Full React frontend (graph view exists but exact visualization is deferred).
- On-demand valuation, one company at a time (synchronous; no queue).

---

## 1. Target backend layout

```
platform/
├── pyproject.toml            # deps + tool config (ruff, mypy, pytest, import-linter)
├── Makefile                  # dev / test / lint / typecheck / run / openapi
├── .env.example              # every setting documented; no secrets
├── README.md
├── src/equity/
│   ├── config.py             # Settings (pydantic-settings), env-driven
│   ├── logging.py            # structlog setup
│   ├── errors.py             # typed exceptions + stable error codes
│   ├── domain/               # PURE. no I/O.
│   │   ├── models.py         # CompanyFinancials, SourceLink
│   │   ├── assumptions.py    # Assumptions + seed_from()
│   │   ├── dcf.py            # DCF: wacc, project, value, sensitivity
│   │   ├── metrics.py        # ratios / core metrics
│   │   └── valuation.py      # DCFResult + result value objects
│   ├── ports/                # interfaces (Protocol/ABC)
│   │   ├── filings.py        # FilingsProvider
│   │   ├── market.py         # MarketDataProvider
│   │   ├── repository.py     # CompanyRepo, ValuationRepo, NoteRepo, TagRepo
│   │   └── search.py         # SearchIndex
│   ├── adapters/             # implement ports; all I/O here
│   │   ├── filings/edgar.py + concepts.py
│   │   ├── market/yfinance.py (+ MockMarketAdapter)
│   │   ├── persistence/sqlite.py + schema.sql + migrations/ + mappers.py
│   │   └── search/fts5.py
│   ├── application/          # use-cases; orchestration only
│   │   ├── container.py      # composition root: ports -> adapters
│   │   ├── ingestion_service.py
│   │   ├── valuation_service.py
│   │   ├── research_service.py
│   │   ├── graph_service.py
│   │   └── search_service.py
│   └── api/                  # FastAPI; thin; no business logic
│       ├── main.py           # app factory, middleware, error handlers
│       ├── deps.py           # DI from container
│       ├── schemas/          # Pydantic DTOs = the API contract
│       └── routers/          # companies, valuations, notes, tags, graph, search
├── tests/{unit,contract,integration,api}/ + conftest.py
└── scripts/{seed_demo.py, live_smoke.py, export_openapi.py}
```

## 2. Frontend layout (Phase 6+)

```
web/
├── package.json, vite.config.ts, tsconfig.json, .env.example
└── src/
    ├── api/{generated/, client.ts, hooks.ts}   # types GENERATED from OpenAPI
    ├── features/{company, notes, sectors, graph, search}/
    ├── components/  lib/  stores/  styles/
```

## 3. Approved dependencies (nothing else without justification)

Backend: fastapi, pydantic, pydantic-settings, numpy, pandas, edgartools,
yfinance, structlog, httpx, uvicorn, pytest, pytest-cov, ruff, mypy,
import-linter. Optional-if-needed: alembic (only if raw-SQL migrations get
unwieldy).

Frontend: react, react-dom, vite, typescript, @tanstack/react-query, zustand,
react-force-graph-2d, openapi-typescript (dev), fuse.js, vitest,
@testing-library/react.

Forbidden in v1: Celery, Redis, any task queue, SQLAlchemy/any ORM, Redux,
GraphQL, any auth framework, Next.js/SSR.

## 4. Dependency rule (enforced by import-linter)
Inward only: `api → application → {domain, ports}`; `adapters → {ports, domain}`.
`domain` imports nothing internal outward. A CI contract encodes this; a
violation fails the build.

## 5. Data contracts (stable shapes)

`CompanyFinancials` (domain): ticker, name, sector, industry, sic; series
(indexed by fiscal year, $M): revenue, ebit, da, capex, nwc, tax_rate; scalars:
total_debt, cash, shares_out ($M / M shares), price, beta; sources: [SourceLink].
Derived: net_debt, market_cap, revenue_cagr(), avg_ebit_margin().

`Assumptions` (domain): horizon, rev_growth, rev_growth_terminal, ebit_margin,
tax_rate, da_pct_rev, capex_pct_rev, nwc_pct_rev, risk_free, equity_premium,
beta, cost_of_debt, target_debt_weight, terminal_growth. `seed_from(fin)` derives
a starting point from history.

`DCFResult` (domain): projection (DataFrame/records), wacc, enterprise_value,
equity_value, fair_value_per_share, upside, warnings[]. Warnings MUST fire when
terminal_growth ≥ wacc and when terminal-value share of EV > 0.75.

These come straight from the validated seed code — preserve the semantics.

## 6. Build order (one phase ≈ one PR; do not skip ahead)

### Phase 0 — Scaffolding
- Create the package skeleton, `pyproject.toml`, `Makefile`, `.env.example`,
  `config.py`, `logging.py`, `errors.py`, and the `import-linter` contract.
- **Accept:** `make lint typecheck` passes on an empty-but-typed skeleton;
  import-linter contract present and passing; `make run` starts an empty FastAPI
  app exposing `/health`.

### Phase 1 — Domain (lift the validated core)
- Port `engine.py` → `domain/dcf.py` + `domain/assumptions.py` +
  `domain/valuation.py`; port the model from `data.py` → `domain/models.py`;
  add `domain/metrics.py`. Strengthen types; keep behavior identical.
- Port the unit tests; add sensitivity + warning-trigger tests.
- **Accept:** domain has zero outward imports (verified); unit tests pass with
  NO network; `mypy --strict` clean; a known-input DCF reproduces the seed
  code's numbers within floating tolerance.

### Phase 2 — Ports + adapters (data in)
- Define `ports/filings.py`, `ports/market.py`. Implement
  `adapters/filings/edgar.py` (+ `concepts.py` fallback tables) and
  `adapters/market/yfinance.py` (+ a `MockMarketAdapter`). Port `market.py`'s
  `enrich` logic into the service layer or adapter as appropriate.
- Contract tests with mocked network (CI-safe). A manual `scripts/live_smoke.py`
  that actually hits EDGAR + Yahoo for one ticker.
- **Accept:** contract tests pass offline in CI; you have RUN `live_smoke.py`
  against a real ticker and pasted the output in the PR (this is the first real
  exercise of the live paths — the prototype couldn't reach these hosts).

### Phase 3 — Persistence
- `ports/repository.py` (Company/Valuation/Note/Tag repos); implement
  `adapters/persistence/sqlite.py` with `schema.sql`, a migration, and mappers.
  Raw SQL — no ORM.
- **Accept:** integration tests use a temp SQLite db; round-trip a company +
  valuation + note + tags; migrations apply cleanly from empty.

### Phase 4 — Valuation service (end-to-end, backend)
- `application/container.py` (composition root), `ingestion_service.py`
  (cache-first: repo → else fetch via adapters → persist), `valuation_service.py`
  (load → DCF → save → return result + sources).
- **Accept:** integration test drives a full valuation for a seeded/mocked
  company without network; source links present on the result; re-running hits
  cache, not the network.

### Phase 5 — API (companies + valuations)
- `api/main.py`, `deps.py`, schemas + routers for companies and valuations.
  `POST /companies/{ticker}/valuation` accepts assumptions, returns result +
  sensitivity + sources. `scripts/export_openapi.py`.
- **Accept:** FastAPI TestClient covers success + validation-error paths;
  OpenAPI exports cleanly; response schema matches the domain contract in §5.

### Phase 6 — Frontend shell + valuation UI
- Vite/React/TS app; generate the TS client from OpenAPI; TanStack Query hooks;
  CompanyWorkspace = HistoricalsTable + AssumptionsPanel + ValuationResult +
  SensitivityGrid. Editing an assumption re-values.
- **Accept:** `tsc --noEmit` clean; the generated client is used (no hand-written
  types for API shapes); a company can be valued and re-valued from the UI
  against the running backend.

### Phase 7 — Notes + tags
- Backend: `research_service.py` (notes CRUD, tag canonicalization/merge),
  routers `notes`, `tags` (GET /tags for autocomplete). Frontend: NoteEditor +
  TagInput with fuse.js fuzzy autocomplete/typo-correction; canonicalize on save.
- **Accept:** tags normalize server-side; fuzzy suggest works client-side;
  notes persist and reload.

### Phase 8 — Search + graph (data layer only for viz)
- `adapters/search/fts5.py`, `search_service.py` (event query → impacted
  tickers), `graph_service.py` (build filtered nodes+edges), routers `search`,
  `graph`. Frontend graph view kept minimal/pluggable — exact visualization is
  DEFERRED per product decision; expose the data + a basic render.
- **Accept:** FTS query over note bodies returns impacted companies; graph
  endpoint returns a filtered subgraph (by sector or by impacted set); a basic
  graph renders. Do not over-invest in visualization polish yet.

## 7. Quality gates (every PR)
`make lint typecheck test` all green; import-linter passes; mypy --strict clean;
no unjustified deps; domain still pure; source links intact. Network-touching
code is mock-tested in CI and live-smoked manually.

## 8. Deploy seam (leave open, don't build)
Repos behind ports → Postgres later is a swap. `config.py` env-driven →
Dockerfile later. Stateless API → scaling is deployment, not code. Batch →
add a `BatchService` calling the existing `ValuationService`; don't build now.

## 9. First message to expect from the human
"Start Phase 0." Do exactly that: scaffold, wire the gates, stop, and report.
Then wait for "Start Phase 1." Proceed phase by phase, reporting at each
boundary, flagging anything ambiguous before diverging.
```
