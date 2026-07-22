"""Mock market adapter — fixed values so wiring runs and tests stay offline.

From the seed core (seed/market.py MockProvider); values approximate the demo
large-cap hardware company used across the domain tests.
"""

from __future__ import annotations

import datetime as _dt

from equity.domain.models import MarketSnapshot


class MockMarketAdapter:
    """Deterministic MarketDataProvider for offline demos and CI."""

    def snapshot(self, ticker: str) -> MarketSnapshot:
        return MarketSnapshot(
            price=195.0,
            shares_out=15550.0,
            total_debt=111088.0,
            cash=61555.0,
            beta=1.28,
            currency="USD",
            as_of=_dt.date.today().isoformat(),
            provider="mock",
            source_url="about:mock-market-data",
            note="synthetic values for offline demo",
        )
