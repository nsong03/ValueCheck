"""Unit tests for domain.models — derived fields against seed-verified values."""

from __future__ import annotations

import pandas as pd
import pytest

from equity.domain.models import CompanyFinancials, SourceLink


class TestDerivedFields:
    def test_net_debt(self, demo_fin: CompanyFinancials) -> None:
        assert demo_fin.net_debt == pytest.approx(49533.0)

    def test_market_cap(self, demo_fin: CompanyFinancials) -> None:
        assert demo_fin.market_cap == pytest.approx(3_032_250.0)

    def test_years(self, demo_fin: CompanyFinancials) -> None:
        assert demo_fin.years == [2019, 2020, 2021, 2022, 2023]

    def test_revenue_cagr_matches_seed(self, demo_fin: CompanyFinancials) -> None:
        # golden: seed/data.py revenue_cagr() on the same figures
        assert demo_fin.revenue_cagr() == pytest.approx(0.10170287389225408, rel=1e-12)

    def test_avg_ebit_margin_matches_seed(self, demo_fin: CompanyFinancials) -> None:
        assert demo_fin.avg_ebit_margin() == pytest.approx(0.27722373146203744, rel=1e-12)


class TestDefaults:
    def test_empty_company_boots_with_defaults(self) -> None:
        fin = CompanyFinancials(ticker="X", name="X Corp", sector="?", industry="?")
        assert fin.years == []
        assert fin.net_debt == 0.0
        assert fin.market_cap == 0.0
        assert fin.revenue_cagr() == 0.0
        assert fin.avg_ebit_margin() == 0.0
        assert fin.sources == []
        assert fin.beta == 1.0

    def test_series_defaults_are_independent(self) -> None:
        a = CompanyFinancials(ticker="A", name="A", sector="?", industry="?")
        b = CompanyFinancials(ticker="B", name="B", sector="?", industry="?")
        a.sources.append(SourceLink("x", "http://example.invalid", "1"))
        assert b.sources == []


class TestHistoricalsTable:
    def test_columns_and_rounding(self, demo_fin: CompanyFinancials) -> None:
        df = demo_fin.historicals_table()
        assert list(df.columns) == [
            "Revenue",
            "EBIT",
            "EBIT margin",
            "D&A",
            "Capex",
            "NWC",
            "Tax rate",
        ]
        assert list(df.index) == demo_fin.years
        # margin column is a rounded ratio
        assert df.loc[2023, "EBIT margin"] == pytest.approx(round(114301 / 383285, 3))


class TestSourceLink:
    def test_str_format(self) -> None:
        s = SourceLink("10-K FY2023", "https://sec.example/doc", "0000-demo")
        assert str(s) == "10-K FY2023 <https://sec.example/doc>"

    def test_frozen(self) -> None:
        s = SourceLink("a", "b", "c")
        with pytest.raises(AttributeError):
            s.label = "mutated"  # type: ignore[misc]


def test_historicals_indexed_by_fiscal_year(demo_fin: CompanyFinancials) -> None:
    assert isinstance(demo_fin.revenue.index, pd.Index)
    assert demo_fin.revenue.loc[2023] == pytest.approx(383285.0)
