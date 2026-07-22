"""Filings port: how the application obtains normalized company financials.

Adapters (Phase 2: SEC EDGAR via edgartools) implement this; the application
layer depends only on this interface. Implementations must return monetary
values in millions USD and attach a SourceLink per filing consumed.
"""

from __future__ import annotations

from typing import Protocol

from equity.domain.models import CompanyFinancials


class FilingsProvider(Protocol):
    """Fetches normalized fundamentals for one company from primary filings."""

    def fetch(self, ticker: str, years: int = 5) -> CompanyFinancials:
        """Return normalized financials for `ticker` covering up to `years`
        fiscal years (oldest -> newest), with the audit trail in `sources`.

        Raises `equity.errors.UpstreamError` (code FILINGS_UNAVAILABLE) when
        the provider cannot serve the company at all; individual missing line
        items yield empty series instead of errors.
        """
        ...
