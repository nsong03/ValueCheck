"""The mock market adapter satisfies the port contract with fixed values."""

from __future__ import annotations

import pytest

from equity.adapters.market.mock import MockMarketAdapter
from equity.domain.models import CompanyFinancials
from equity.ports.market import MarketDataProvider

pytestmark = pytest.mark.contract


def test_satisfies_port_protocol() -> None:
    provider: MarketDataProvider = MockMarketAdapter()  # structural check
    snap = provider.snapshot("DEMO")
    assert snap.is_complete()
    assert snap.provider == "mock"


def test_enriches_a_bare_company() -> None:
    fin = CompanyFinancials(ticker="DEMO", name="Demo", sector="?", industry="?")
    fin.apply_market_snapshot(MockMarketAdapter().snapshot("DEMO"))
    assert fin.price == 195.0
    assert fin.shares_out == 15550.0
    assert fin.net_debt == pytest.approx(49533.0)
    assert fin.beta == 1.28
    assert len(fin.sources) == 1
    assert "mock" in fin.sources[0].label
