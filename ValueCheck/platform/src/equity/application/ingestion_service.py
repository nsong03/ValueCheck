"""Ingestion: get a company's normalized financials, cache-first.

Flow (BUILD_SPEC Phase 4): repository hit -> return it; miss (or explicit
refresh) -> fetch filings via the FilingsProvider port, enrich with a market
snapshot via the MarketDataProvider port, persist, return. Orchestration
only — normalization lives in the adapters, math in the domain.
"""

from __future__ import annotations

from equity.domain.models import CompanyFinancials
from equity.logging import get_logger
from equity.ports.filings import FilingsProvider
from equity.ports.market import MarketDataProvider
from equity.ports.repository import CompanyRepo

log = get_logger(__name__)


class IngestionService:
    def __init__(
        self,
        companies: CompanyRepo,
        filings: FilingsProvider,
        market: MarketDataProvider,
    ) -> None:
        self._companies = companies
        self._filings = filings
        self._market = market

    def get_company(
        self,
        ticker: str,
        *,
        years: int = 5,
        refresh: bool = False,
    ) -> CompanyFinancials:
        """Return normalized financials for `ticker`, hitting the network only
        on a cache miss or an explicit `refresh=True`.

        Raises `UpstreamError` when a live fetch is needed but fails; cached
        companies never touch the network.
        """
        symbol = ticker.upper().strip()
        if not refresh:
            cached = self._companies.get(symbol)
            if cached is not None:
                log.info("ingestion.cache_hit", ticker=symbol)
                return cached

        log.info("ingestion.fetching", ticker=symbol, years=years, refresh=refresh)
        fin = self._filings.fetch(symbol, years=years)
        snap = self._market.snapshot(symbol)
        fin.apply_market_snapshot(snap)
        self._companies.save(fin)
        log.info(
            "ingestion.stored",
            ticker=symbol,
            revenue_years=len(fin.revenue),
            sources=len(fin.sources),
            market_complete=snap.is_complete(),
        )
        return fin
