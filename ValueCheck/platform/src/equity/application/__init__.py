"""Application layer: use-cases and the composition root.

Orchestration only — no business math (that lives in the domain) and no I/O
(that lives in adapters):

- `container` — composition root binding ports to adapters
- `ingestion_service` — cache-first company financials
- `valuation_service` — load -> DCF -> save -> result + sources
"""
