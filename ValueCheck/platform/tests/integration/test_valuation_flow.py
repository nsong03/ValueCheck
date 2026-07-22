"""Phase 4 acceptance: full valuation end-to-end, offline, cache-first.

Fake providers stand in for the network adapters; everything else is real
(SQLite repos on a temp db, domain DCF, services, composition root).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from equity.adapters.filings.edgar import EdgarFilingsSource
from equity.adapters.market.mock import MockMarketAdapter
from equity.adapters.market.yfinance import YFinanceProvider
from equity.application.container import Container, build_container
from equity.config import Settings
from equity.domain.assumptions import Assumptions
from equity.domain.models import CompanyFinancials, MarketSnapshot
from equity.errors import ErrorCode, UpstreamError

pytestmark = pytest.mark.integration

# Phase 1 golden number: seed engine fair value/share for the demo company
GOLDEN_FAIR_VALUE = 98.31624329048412


class FakeFilings:
    """Returns the demo company WITHOUT capital-structure fields, so market
    enrichment is observable. Counts calls to prove cache behavior."""

    def __init__(self, factory: Callable[..., CompanyFinancials]) -> None:
        self._factory = factory
        self.calls = 0
        self.fail_with: UpstreamError | None = None

    def fetch(self, ticker: str, years: int = 5) -> CompanyFinancials:
        self.calls += 1
        if self.fail_with is not None:
            raise self.fail_with
        fin = self._factory(years=years)
        fin.ticker = ticker.upper()
        fin.total_debt = 0.0
        fin.cash = 0.0
        fin.shares_out = 0.0
        fin.price = 0.0
        fin.beta = 1.0  # counts as unset; market beta must take over
        return fin


class CountingMarket:
    """MockMarketAdapter + call counting (values match the demo company)."""

    def __init__(self) -> None:
        self._inner = MockMarketAdapter()
        self.calls = 0

    def snapshot(self, ticker: str) -> MarketSnapshot:
        self.calls += 1
        return self._inner.snapshot(ticker)


@pytest.fixture
def fake_filings(demo_factory: Callable[..., CompanyFinancials]) -> FakeFilings:
    return FakeFilings(demo_factory)


@pytest.fixture
def market() -> CountingMarket:
    return CountingMarket()


@pytest.fixture
def container(tmp_path: Path, fake_filings: FakeFilings, market: CountingMarket) -> Container:
    settings = Settings(database_path=tmp_path / "flow.db")
    return build_container(settings, filings=fake_filings, market=market)


class TestFullValuationOffline:
    def test_result_reproduces_golden_number(self, container: Container) -> None:
        """Filings + market enrichment + seeded DCF == the Phase 1 golden run."""
        outcome = container.valuation.value("DEMO")
        assert outcome.result.fair_value_per_share == pytest.approx(GOLDEN_FAIR_VALUE, rel=1e-9)
        assert outcome.sensitivity.shape == (5, 5)

    def test_source_links_present_on_result(self, container: Container) -> None:
        outcome = container.valuation.value("DEMO")
        sources = outcome.result.fin.sources
        assert len(sources) == 6  # 5 filings + 1 market snapshot
        assert any("10-K" in s.label for s in sources)
        assert any("mock" in s.accession for s in sources)

    def test_run_is_persisted(self, container: Container) -> None:
        outcome = container.valuation.value("DEMO")
        stored = container.valuation.get(outcome.record.id)
        assert stored is not None
        assert stored.fair_value_per_share == outcome.result.fair_value_per_share
        assert stored.assumptions == outcome.result.assumptions

    def test_company_is_cached(self, container: Container) -> None:
        container.valuation.value("DEMO")
        cached = container.companies.get("DEMO")
        assert cached is not None
        assert cached.price == 195.0  # market enrichment persisted too


class TestCacheFirst:
    def test_second_run_hits_cache_not_network(
        self, container: Container, fake_filings: FakeFilings, market: CountingMarket
    ) -> None:
        container.valuation.value("DEMO")
        container.valuation.value("DEMO")
        assert fake_filings.calls == 1  # network touched exactly once
        assert market.calls == 1

    def test_each_run_still_persists_a_record(self, container: Container) -> None:
        first = container.valuation.value("DEMO")
        second = container.valuation.value("DEMO")
        history = container.valuation.history("DEMO")
        assert [r.id for r in history] == [second.record.id, first.record.id]

    def test_refresh_forces_refetch(self, container: Container, fake_filings: FakeFilings) -> None:
        container.valuation.value("DEMO")
        container.valuation.value("DEMO", refresh=True)
        assert fake_filings.calls == 2

    def test_ticker_normalized(self, container: Container, fake_filings: FakeFilings) -> None:
        container.valuation.value("demo")
        container.valuation.value("  DEMO  ")
        assert fake_filings.calls == 1
        assert container.companies.list_tickers() == ["DEMO"]


class TestAssumptionOverrides:
    def test_custom_assumptions_used_and_persisted(self, container: Container) -> None:
        fin = container.ingestion.get_company("DEMO")
        a = Assumptions.seed_from(fin)
        a.ebit_margin = 0.29
        a.terminal_growth = 0.025
        outcome = container.valuation.value("DEMO", a)
        assert outcome.result.assumptions.ebit_margin == 0.29
        stored = container.valuation.get(outcome.record.id)
        assert stored is not None
        assert stored.assumptions.ebit_margin == 0.29


class TestFailures:
    def test_upstream_failure_propagates(
        self, container: Container, fake_filings: FakeFilings
    ) -> None:
        fake_filings.fail_with = UpstreamError("sec down", code=ErrorCode.FILINGS_UNAVAILABLE)
        with pytest.raises(UpstreamError):
            container.valuation.value("DEMO")
        assert container.companies.get("DEMO") is None  # nothing half-saved

    def test_cached_company_survives_upstream_outage(
        self, container: Container, fake_filings: FakeFilings
    ) -> None:
        container.valuation.value("DEMO")
        fake_filings.fail_with = UpstreamError("sec down", code=ErrorCode.FILINGS_UNAVAILABLE)
        outcome = container.valuation.value("DEMO")  # cache-first: still works
        assert outcome.result.fair_value_per_share == pytest.approx(GOLDEN_FAIR_VALUE, rel=1e-9)


class TestContainerDefaults:
    def test_default_container_wires_live_adapters_offline(self, tmp_path: Path) -> None:
        """Building the default graph needs neither network nor identity."""
        settings = Settings(database_path=tmp_path / "default.db", edgar_identity=None)
        c = build_container(settings)
        assert isinstance(c.filings, EdgarFilingsSource)
        assert isinstance(c.market, YFinanceProvider)
        assert (tmp_path / "default.db").exists()  # migrations applied
        assert c.companies.list_tickers() == []
