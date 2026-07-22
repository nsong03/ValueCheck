"""Pure domain layer. Zero I/O: no network, disk, env, or logging side effects.

Lifted from the validated seed core (seed/engine.py, seed/data.py) in Phase 1:

- `models` — SourceLink + CompanyFinancials (the one normalized shape)
- `metrics` — core ratio calculations over fiscal-year series
- `assumptions` — Assumptions + seed_from()
- `dcf` — the DCF engine: wacc, project, value, sensitivity
- `valuation` — DCFResult value object
"""
