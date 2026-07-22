"""Contract tests for the EDGAR adapter — mocked network, CI-safe.

A fake `edgar` module is injected into sys.modules so the adapter's lazy
`import edgar` binds to it. Fakes mirror the REAL edgartools 5.x FactQuery
surface observed in the Phase 2 live probe: chainable
query().by_concept().by_fiscal_period().by_period_length().to_dataframe(),
values in absolute dollars, restated periods repeated across filings.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pandas as pd
import pytest

from equity.adapters.filings.concepts import CONCEPTS
from equity.adapters.filings.edgar import EdgarFilingsSource
from equity.errors import ErrorCode, UpstreamError

pytestmark = pytest.mark.contract

PRETAX_CONCEPT = CONCEPTS["pretax"][0]


def fact_rows(concept: str, rows: list[tuple[str, str, float, str]]) -> pd.DataFrame:
    """rows: (period_start, period_end, value_in_dollars, filing_date)."""
    return pd.DataFrame(
        {
            "concept": [f"us-gaap:{concept}"] * len(rows),
            "numeric_value": [r[2] for r in rows],
            "period_start": [r[0] for r in rows],
            "period_end": [r[1] for r in rows],
            "filing_date": [r[3] for r in rows],
            "fiscal_period": ["FY"] * len(rows),
        }
    )


class FakeQuery:
    def __init__(self, tables: dict[str, pd.DataFrame], calls: list[str]) -> None:
        self._tables = tables
        self._concept: str | None = None
        self._calls = calls

    def by_concept(self, concept: str) -> FakeQuery:
        self._concept = concept
        self._calls.append(f"by_concept:{concept}")
        return self

    def by_fiscal_period(self, period: str) -> FakeQuery:
        self._calls.append(f"by_fiscal_period:{period}")
        return self

    def by_period_length(self, months: int) -> FakeQuery:
        self._calls.append(f"by_period_length:{months}")
        return self

    def to_dataframe(self) -> pd.DataFrame:
        assert self._concept is not None
        return self._tables.get(self._concept, pd.DataFrame())


class FakeFacts:
    def __init__(self, tables: dict[str, pd.DataFrame], calls: list[str]) -> None:
        self._tables = tables
        self._calls = calls

    def query(self) -> FakeQuery:
        return FakeQuery(self._tables, self._calls)


class FakeFiling:
    def __init__(self, date: str, accession: str) -> None:
        self.filing_date = date
        self.accession_no = accession
        self.homepage_url = f"https://sec.example/{accession}-index.html"


class FakeFilings:
    def __init__(self, filings: list[FakeFiling]) -> None:
        self._filings = filings

    def head(self, n: int) -> list[FakeFiling]:
        return self._filings[:n]


class FakeCompany:
    name = "Test Corp"
    sector = None  # matches live edgartools: sector attr exists but is None
    industry = "Widgets"
    sic = 1234

    def __init__(self, tables: dict[str, pd.DataFrame], calls: list[str]) -> None:
        self._tables = tables
        self._calls = calls

    def get_facts(self) -> FakeFacts:
        return FakeFacts(self._tables, self._calls)

    def get_filings(self, form: str) -> FakeFilings:
        assert form == "10-K"
        return FakeFilings(
            [FakeFiling("2025-10-31", "acc-2025"), FakeFiling("2024-11-01", "acc-2024")]
        )


def install_fake_edgar(
    monkeypatch: pytest.MonkeyPatch,
    tables: dict[str, pd.DataFrame],
    calls: list[str],
    identities: list[str],
    company_error: Exception | None = None,
) -> None:
    fake = types.ModuleType("edgar")

    def set_identity(identity: str) -> None:
        identities.append(identity)

    def company(ticker: str) -> Any:
        if company_error is not None:
            raise company_error
        return FakeCompany(tables, calls)

    fake.set_identity = set_identity  # type: ignore[attr-defined]
    fake.Company = company  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "edgar", fake)


REVENUE_ROWS = fact_rows(
    "Revenues",
    [
        # restated period: two filings report FY-2023; the later filing wins
        ("2022-10-01", "2023-09-30", 100_000_000_000.0, "2023-11-03"),
        ("2022-10-01", "2023-09-30", 101_000_000_000.0, "2024-11-01"),
        ("2023-10-01", "2024-09-28", 110_000_000_000.0, "2024-11-01"),
        ("2024-09-29", "2025-09-27", 120_000_000_000.0, "2025-10-31"),
    ],
)

CAPEX_ROWS = fact_rows(
    "PaymentsToAcquirePropertyPlantAndEquipment",
    [
        ("2023-10-01", "2024-09-28", -9_000_000_000.0, "2024-11-01"),  # negative in filing
        ("2024-09-29", "2025-09-27", -10_000_000_000.0, "2025-10-31"),
    ],
)

PRETAX_ROWS = fact_rows(
    PRETAX_CONCEPT,
    [
        ("2023-10-01", "2024-09-28", 10_000_000_000.0, "2024-11-01"),
        ("2024-09-29", "2025-09-27", 20_000_000_000.0, "2025-10-31"),
    ],
)

TAX_ROWS = pd.concat(
    [
        fact_rows(
            "IncomeTaxExpenseBenefit",
            [
                ("2023-10-01", "2024-09-28", 8_000_000_000.0, "2024-11-01"),  # 80% -> clip 50%
                ("2024-09-29", "2025-09-27", 3_000_000_000.0, "2025-10-31"),  # 15%
            ],
        ),
        # Live finding (AAPL smoke): by_concept matches fuzzily and also returns
        # DeferredIncomeTaxExpenseBenefit rows; the adapter must drop them even
        # when they were filed later than the exact-concept rows.
        fact_rows(
            "DeferredIncomeTaxExpenseBenefit",
            [
                ("2023-10-01", "2024-09-28", -70_000_000.0, "2025-10-31"),
                ("2024-09-29", "2025-09-27", 80_000_000.0, "2025-12-31"),
            ],
        ),
    ],
    ignore_index=True,
)

TABLES = {
    "Revenues": REVENUE_ROWS,
    "PaymentsToAcquirePropertyPlantAndEquipment": CAPEX_ROWS,
    PRETAX_CONCEPT: PRETAX_ROWS,
    "IncomeTaxExpenseBenefit": TAX_ROWS,
}


class TestFetch:
    @pytest.fixture
    def fetched(self, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, list[str], list[str]]:
        calls: list[str] = []
        identities: list[str] = []
        install_fake_edgar(monkeypatch, TABLES, calls, identities)
        fin = EdgarFilingsSource("Jane Doe jane@example.com").fetch("test", years=5)
        return fin, calls, identities

    def test_identity_is_set_from_constructor(
        self, fetched: tuple[Any, list[str], list[str]]
    ) -> None:
        _, _, identities = fetched
        assert identities == ["Jane Doe jane@example.com"]

    def test_concept_fallback_order(self, fetched: tuple[Any, list[str], list[str]]) -> None:
        _, calls, _ = fetched
        # first revenue concept has no data -> adapter must try it, then fall back
        assert calls.index("by_concept:RevenueFromContractWithCustomerExcludingAssessedTax") < (
            calls.index("by_concept:Revenues")
        )

    def test_annual_filter_applied(self, fetched: tuple[Any, list[str], list[str]]) -> None:
        _, calls, _ = fetched
        assert "by_fiscal_period:FY" in calls
        assert "by_period_length:12" in calls

    def test_values_scaled_to_millions(self, fetched: tuple[Any, list[str], list[str]]) -> None:
        fin, _, _ = fetched
        assert fin.revenue.loc[2024] == pytest.approx(110_000.0)
        assert fin.revenue.loc[2025] == pytest.approx(120_000.0)

    def test_restatement_dedupe_latest_filing_wins(
        self, fetched: tuple[Any, list[str], list[str]]
    ) -> None:
        fin, _, _ = fetched
        assert fin.revenue.loc[2023] == pytest.approx(101_000.0)  # not 100_000

    def test_series_indexed_by_period_end_year(
        self, fetched: tuple[Any, list[str], list[str]]
    ) -> None:
        fin, _, _ = fetched
        assert list(fin.revenue.index) == [2023, 2024, 2025]

    def test_capex_absolute_value(self, fetched: tuple[Any, list[str], list[str]]) -> None:
        fin, _, _ = fetched
        assert fin.capex.loc[2025] == pytest.approx(10_000.0)  # sign flipped

    def test_tax_rate_ratio_clipped(self, fetched: tuple[Any, list[str], list[str]]) -> None:
        fin, _, _ = fetched
        assert fin.tax_rate.loc[2024] == pytest.approx(0.5)  # 80% clipped
        assert fin.tax_rate.loc[2025] == pytest.approx(0.15)

    def test_missing_concepts_give_empty_series(
        self, fetched: tuple[Any, list[str], list[str]]
    ) -> None:
        fin, _, _ = fetched
        assert len(fin.ebit) == 0  # no OperatingIncomeLoss in fixtures
        assert len(fin.da) == 0

    def test_company_metadata(self, fetched: tuple[Any, list[str], list[str]]) -> None:
        fin, _, _ = fetched
        assert fin.ticker == "TEST"  # upper-cased
        assert fin.name == "Test Corp"
        assert fin.sector == "Unknown"  # None attr -> "Unknown"
        assert fin.industry == "Widgets"
        assert fin.sic == "1234"

    def test_source_links_from_10ks(self, fetched: tuple[Any, list[str], list[str]]) -> None:
        fin, _, _ = fetched
        assert [s.accession for s in fin.sources] == ["acc-2025", "acc-2024"]
        assert fin.sources[0].label == "10-K 2025-10-31"
        assert fin.sources[0].url.endswith("acc-2025-index.html")


class TestErrors:
    def test_missing_identity_raises(self) -> None:
        with pytest.raises(UpstreamError) as ei:
            EdgarFilingsSource("")
        assert ei.value.code is ErrorCode.FILINGS_UNAVAILABLE

    def test_company_lookup_failure_raises_upstream(self, monkeypatch: pytest.MonkeyPatch) -> None:
        install_fake_edgar(monkeypatch, {}, [], [], company_error=RuntimeError("SEC unreachable"))
        with pytest.raises(UpstreamError) as ei:
            EdgarFilingsSource("Jane Doe jane@example.com").fetch("TEST")
        assert ei.value.code is ErrorCode.FILINGS_UNAVAILABLE
        assert "SEC unreachable" in ei.value.message
