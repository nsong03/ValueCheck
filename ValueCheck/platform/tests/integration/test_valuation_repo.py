"""Valuation repository round-trip: stored runs reproduce the engine output."""

from __future__ import annotations

import pandas as pd
import pytest

from equity.adapters.persistence.sqlite import SQLiteCompanyRepo, SQLiteValuationRepo
from equity.domain.assumptions import Assumptions
from equity.domain.dcf import DCF
from equity.domain.models import CompanyFinancials
from equity.errors import PersistenceError

pytestmark = pytest.mark.integration


@pytest.fixture
def saved_company(
    company_repo: SQLiteCompanyRepo, demo_fin: CompanyFinancials
) -> CompanyFinancials:
    company_repo.save(demo_fin)
    return demo_fin


class TestRoundTrip:
    def test_save_returns_stored_record(
        self, valuation_repo: SQLiteValuationRepo, saved_company: CompanyFinancials
    ) -> None:
        result = DCF(saved_company).value()
        record = valuation_repo.save(result)

        assert record.id >= 1
        assert record.ticker == "DEMO"
        assert record.created_at is not None
        assert record.wacc == result.wacc  # JSON/REAL round-trip is exact
        assert record.enterprise_value == result.enterprise_value
        assert record.equity_value == result.equity_value
        assert record.fair_value_per_share == result.fair_value_per_share
        assert record.upside == result.upside
        assert record.warnings == result.warnings

    def test_assumptions_round_trip_exactly(
        self, valuation_repo: SQLiteValuationRepo, saved_company: CompanyFinancials
    ) -> None:
        a = Assumptions.seed_from(saved_company)
        a.ebit_margin = 0.29
        result = DCF(saved_company, a).value()
        record = valuation_repo.save(result)
        loaded = valuation_repo.get(record.id)

        assert loaded is not None
        assert loaded.assumptions == a  # dataclass equality, field for field

    def test_projection_round_trips_exactly(
        self, valuation_repo: SQLiteValuationRepo, saved_company: CompanyFinancials
    ) -> None:
        result = DCF(saved_company).value()
        record = valuation_repo.save(result)
        loaded = valuation_repo.get(record.id)

        assert loaded is not None
        pd.testing.assert_frame_equal(loaded.projection, result.projection)

    def test_warnings_round_trip(
        self, valuation_repo: SQLiteValuationRepo, saved_company: CompanyFinancials
    ) -> None:
        a = Assumptions.seed_from(saved_company)
        a.terminal_growth = 0.09  # TV dominates EV -> warning fires
        result = DCF(saved_company, a).value()
        assert result.warnings  # precondition
        record = valuation_repo.save(result)
        loaded = valuation_repo.get(record.id)
        assert loaded is not None
        assert loaded.warnings == result.warnings


class TestListing:
    def test_list_for_newest_first(
        self, valuation_repo: SQLiteValuationRepo, saved_company: CompanyFinancials
    ) -> None:
        first = valuation_repo.save(DCF(saved_company).value())
        second = valuation_repo.save(DCF(saved_company).value())
        records = valuation_repo.list_for("DEMO")
        assert [r.id for r in records] == [second.id, first.id]

    def test_list_for_unknown_ticker_empty(self, valuation_repo: SQLiteValuationRepo) -> None:
        assert valuation_repo.list_for("NOPE") == []

    def test_get_missing_returns_none(self, valuation_repo: SQLiteValuationRepo) -> None:
        assert valuation_repo.get(12345) is None


class TestIntegrity:
    def test_saving_without_company_raises(
        self, valuation_repo: SQLiteValuationRepo, demo_fin: CompanyFinancials
    ) -> None:
        # company never saved -> FK violation surfaces as PersistenceError
        result = DCF(demo_fin).value()
        with pytest.raises(PersistenceError):
            valuation_repo.save(result)

    def test_deleting_company_cascades_valuations(
        self,
        company_repo: SQLiteCompanyRepo,
        valuation_repo: SQLiteValuationRepo,
        saved_company: CompanyFinancials,
    ) -> None:
        record = valuation_repo.save(DCF(saved_company).value())
        company_repo.delete("DEMO")
        assert valuation_repo.get(record.id) is None
