"""Company repository round-trip against a temp SQLite database."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import pytest

from equity.adapters.persistence.sqlite import SQLiteCompanyRepo
from equity.domain.models import CompanyFinancials

pytestmark = pytest.mark.integration


class TestRoundTrip:
    def test_full_round_trip(
        self, company_repo: SQLiteCompanyRepo, demo_fin: CompanyFinancials
    ) -> None:
        company_repo.save(demo_fin)
        loaded = company_repo.get("DEMO")

        assert loaded is not None
        assert loaded.ticker == demo_fin.ticker
        assert loaded.name == demo_fin.name
        assert loaded.sector == demo_fin.sector
        assert loaded.industry == demo_fin.industry
        assert loaded.sic == demo_fin.sic
        for metric in ("revenue", "ebit", "da", "capex", "nwc", "tax_rate"):
            pd.testing.assert_series_equal(
                getattr(loaded, metric),
                getattr(demo_fin, metric),
                check_names=False,
                obj=metric,
            )
        assert loaded.total_debt == demo_fin.total_debt
        assert loaded.cash == demo_fin.cash
        assert loaded.shares_out == demo_fin.shares_out
        assert loaded.price == demo_fin.price
        assert loaded.beta == demo_fin.beta
        assert loaded.sources == demo_fin.sources  # order + content preserved

    def test_derived_values_survive(
        self, company_repo: SQLiteCompanyRepo, demo_fin: CompanyFinancials
    ) -> None:
        company_repo.save(demo_fin)
        loaded = company_repo.get("DEMO")
        assert loaded is not None
        assert loaded.net_debt == pytest.approx(demo_fin.net_debt)
        assert loaded.revenue_cagr() == pytest.approx(demo_fin.revenue_cagr(), rel=1e-12)
        assert loaded.avg_ebit_margin() == pytest.approx(demo_fin.avg_ebit_margin(), rel=1e-12)

    def test_nan_series_entries_round_trip_as_missing(
        self, company_repo: SQLiteCompanyRepo, demo_fin: CompanyFinancials
    ) -> None:
        demo_fin.da.iloc[2] = float("nan")
        company_repo.save(demo_fin)
        loaded = company_repo.get("DEMO")
        assert loaded is not None
        # NaN year is simply absent from the stored series
        assert 2021 not in loaded.da.index
        assert len(loaded.da) == 4


class TestUpsert:
    def test_save_twice_updates_in_place(
        self, company_repo: SQLiteCompanyRepo, demo_fin: CompanyFinancials
    ) -> None:
        company_repo.save(demo_fin)
        demo_fin.price = 210.0
        demo_fin.revenue.iloc[-1] = 400_000.0
        company_repo.save(demo_fin)

        loaded = company_repo.get("DEMO")
        assert loaded is not None
        assert loaded.price == 210.0
        assert loaded.revenue.iloc[-1] == 400_000.0
        assert len(loaded.revenue) == 5  # replaced, not duplicated
        assert len(loaded.sources) == 5

    def test_list_tickers(
        self,
        company_repo: SQLiteCompanyRepo,
        demo_factory: Callable[..., CompanyFinancials],
    ) -> None:
        b = demo_factory()
        b.ticker = "BBB"
        a = demo_factory()
        a.ticker = "AAA"
        company_repo.save(b)
        company_repo.save(a)
        assert company_repo.list_tickers() == ["AAA", "BBB"]


class TestMissingAndDelete:
    def test_get_missing_returns_none(self, company_repo: SQLiteCompanyRepo) -> None:
        assert company_repo.get("NOPE") is None

    def test_delete(self, company_repo: SQLiteCompanyRepo, demo_fin: CompanyFinancials) -> None:
        company_repo.save(demo_fin)
        assert company_repo.delete("DEMO") is True
        assert company_repo.get("DEMO") is None
        assert company_repo.delete("DEMO") is False
