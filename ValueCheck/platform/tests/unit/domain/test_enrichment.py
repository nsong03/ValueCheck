"""Unit tests for CompanyFinancials.apply_market_snapshot (pure enrich logic)."""

from __future__ import annotations

import pytest

from equity.domain.models import CompanyFinancials, MarketSnapshot


def snap(**overrides: object) -> MarketSnapshot:
    base: dict[str, object] = {
        "price": 100.0,
        "shares_out": 1000.0,
        "total_debt": 500.0,
        "cash": 200.0,
        "beta": 1.5,
        "provider": "test-provider",
        "as_of": "2026-07-21",
        "source_url": "https://example.invalid/quote/X",
    }
    base.update(overrides)
    return MarketSnapshot(**base)  # type: ignore[arg-type]


@pytest.fixture
def bare_fin() -> CompanyFinancials:
    return CompanyFinancials(ticker="X", name="X Corp", sector="?", industry="?")


class TestFillsUnsetFields:
    def test_fills_everything_on_bare_company(self, bare_fin: CompanyFinancials) -> None:
        bare_fin.apply_market_snapshot(snap())
        assert bare_fin.price == 100.0
        assert bare_fin.shares_out == 1000.0
        assert bare_fin.total_debt == 500.0
        assert bare_fin.cash == 200.0
        assert bare_fin.beta == 1.5

    def test_preserves_hand_entered_values(self, bare_fin: CompanyFinancials) -> None:
        bare_fin.price = 42.0
        bare_fin.total_debt = 999.0
        bare_fin.apply_market_snapshot(snap())
        assert bare_fin.price == 42.0  # untouched
        assert bare_fin.total_debt == 999.0  # untouched
        assert bare_fin.shares_out == 1000.0  # was unset -> filled

    def test_overwrite_replaces_everything(self, bare_fin: CompanyFinancials) -> None:
        bare_fin.price = 42.0
        bare_fin.beta = 0.77
        bare_fin.apply_market_snapshot(snap(), overwrite=True)
        assert bare_fin.price == 100.0
        assert bare_fin.beta == 1.5


class TestBetaRule:
    """Beta 0.0/1.0 count as unset (1.0 is the class default, not data)."""

    def test_default_beta_replaced(self, bare_fin: CompanyFinancials) -> None:
        assert bare_fin.beta == 1.0
        bare_fin.apply_market_snapshot(snap(beta=1.3))
        assert bare_fin.beta == 1.3

    def test_zero_beta_replaced(self, bare_fin: CompanyFinancials) -> None:
        bare_fin.beta = 0.0
        bare_fin.apply_market_snapshot(snap(beta=1.3))
        assert bare_fin.beta == 1.3

    def test_custom_beta_preserved(self, bare_fin: CompanyFinancials) -> None:
        bare_fin.beta = 0.9
        bare_fin.apply_market_snapshot(snap(beta=1.3))
        assert bare_fin.beta == 0.9


class TestAuditTrail:
    def test_source_link_appended(self, bare_fin: CompanyFinancials) -> None:
        bare_fin.apply_market_snapshot(snap())
        assert len(bare_fin.sources) == 1
        src = bare_fin.sources[0]
        assert src.label == "Market data (test-provider, 2026-07-21)"
        assert src.url == "https://example.invalid/quote/X"
        assert src.accession == "test-provider"

    def test_existing_sources_kept(self, bare_fin: CompanyFinancials) -> None:
        bare_fin.apply_market_snapshot(snap())
        bare_fin.apply_market_snapshot(snap(), overwrite=True)
        assert len(bare_fin.sources) == 2


class TestSnapshotCompleteness:
    def test_complete(self) -> None:
        assert snap().is_complete()

    def test_nan_field_incomplete(self) -> None:
        assert not snap(price=float("nan")).is_complete()
