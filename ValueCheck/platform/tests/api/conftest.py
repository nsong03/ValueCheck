"""API test fixtures: TestClient over a real app with fake network adapters.

Everything below the ports is real (services, SQLite on a temp db, domain);
only the network edges are faked — same shape as the Phase 4 flow tests.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from equity.adapters.market.mock import MockMarketAdapter
from equity.api.main import create_app
from equity.application.container import Container, build_container
from equity.config import Settings
from equity.domain.models import CompanyFinancials, MarketSnapshot
from equity.errors import UpstreamError


class FakeFilings:
    """Demo company without capital structure; counts calls; can fail."""

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
        fin.beta = 1.0
        return fin


class FakeMarket:
    """MockMarketAdapter values, with an overridable snapshot for edge cases."""

    def __init__(self) -> None:
        self._inner = MockMarketAdapter()
        self.calls = 0
        self.override: MarketSnapshot | None = None

    def snapshot(self, ticker: str) -> MarketSnapshot:
        self.calls += 1
        return self.override if self.override is not None else self._inner.snapshot(ticker)


@pytest.fixture
def fake_filings(demo_factory: Callable[..., CompanyFinancials]) -> FakeFilings:
    return FakeFilings(demo_factory)


@pytest.fixture
def fake_market() -> FakeMarket:
    return FakeMarket()


@pytest.fixture
def container(tmp_path: Path, fake_filings: FakeFilings, fake_market: FakeMarket) -> Container:
    settings = Settings(database_path=tmp_path / "api.db", environment="ci")
    return build_container(settings, filings=fake_filings, market=fake_market)


@pytest.fixture
def client(container: Container) -> TestClient:
    app = create_app(container.settings, container)
    return TestClient(app)
