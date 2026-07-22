"""Market-data port: current capital-structure inputs for the DCF bridge.

Fills what XBRL doesn't give cleanly: price, shares outstanding, total debt,
cash, and beta. These feed WACC (beta), the enterprise->equity bridge
(net debt), and the per-share result (price, shares). Providers are swappable
(yfinance today; OpenBB / a paid feed tomorrow) — the engine never sees this
interface, only the fields applied onto a CompanyFinancials.
"""

from __future__ import annotations

from typing import Protocol

from equity.domain.models import MarketSnapshot


class MarketDataProvider(Protocol):
    """Returns a point-in-time market snapshot for one ticker."""

    def snapshot(self, ticker: str) -> MarketSnapshot:
        """Fetch current market data, in millions USD (shares in millions).

        Implementations degrade gracefully: missing fields become 0.0 (or a
        defaulted beta of 1.0) with an explanatory `note`, rather than raising.
        Raises `equity.errors.UpstreamError` (code MARKET_DATA_UNAVAILABLE)
        only when the provider cannot serve the ticker at all.
        """
        ...
