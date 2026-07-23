"""Screener service: one row per company, joining financials, latest
valuation, tags, and current research attributes (Phase 9)."""

from __future__ import annotations

import pytest

from equity.adapters.persistence.sqlite import (
    SQLiteAttributeRepo,
    SQLiteCompanyRepo,
    SQLiteNoteRepo,
    SQLiteValuationRepo,
)
from equity.application.attribute_service import AttributeService
from equity.application.screener_service import ScreenerService
from equity.domain.dcf import DCF
from equity.domain.models import CompanyFinancials
from equity.domain.research import Note

pytestmark = pytest.mark.integration


@pytest.fixture
def screener(
    company_repo: SQLiteCompanyRepo,
    valuation_repo: SQLiteValuationRepo,
    note_repo: SQLiteNoteRepo,
    attribute_repo: SQLiteAttributeRepo,
) -> ScreenerService:
    return ScreenerService(company_repo, valuation_repo, note_repo, attribute_repo)


@pytest.fixture
def attributes(attribute_repo: SQLiteAttributeRepo) -> AttributeService:
    return AttributeService(attribute_repo)


def test_row_combines_financials_valuation_tags_and_attributes(
    screener: ScreenerService,
    company_repo: SQLiteCompanyRepo,
    valuation_repo: SQLiteValuationRepo,
    note_repo: SQLiteNoteRepo,
    attributes: AttributeService,
    demo_fin: CompanyFinancials,
) -> None:
    company_repo.save(demo_fin)
    loaded = company_repo.get("DEMO")
    assert loaded is not None
    result = DCF(loaded).value()
    valuation_repo.save(result)
    note_repo.save(Note(ticker="DEMO", title="t", body="", tags=["moat", "hardware"]))
    attributes.set_value("DEMO", "quality.moat", "4", source="note", value_type="scale")

    rows = screener.build_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row.ticker == "DEMO"
    assert row.tags == ["hardware", "moat"]
    assert row.note_count == 1
    assert row.latest_valuation is not None
    assert row.latest_valuation.fair_value_per_share == result.fair_value_per_share
    assert row.attributes["quality.moat"].value == "4"


def test_row_without_valuation_notes_or_attributes(
    screener: ScreenerService, company_repo: SQLiteCompanyRepo, demo_fin: CompanyFinancials
) -> None:
    company_repo.save(demo_fin)
    row = screener.build_rows()[0]
    assert row.latest_valuation is None
    assert row.tags == []
    assert row.note_count == 0
    assert row.attributes == {}


def test_multiple_companies_each_get_their_own_row(
    screener: ScreenerService,
    company_repo: SQLiteCompanyRepo,
    attributes: AttributeService,
    demo_fin: CompanyFinancials,
) -> None:
    company_repo.save(demo_fin)
    other = CompanyFinancials(ticker="OTHER", name="Other Inc.", sector="Energy", industry="Oil")
    company_repo.save(other)
    attributes.set_value("DEMO", "region", "us", source="note")
    attributes.set_value("OTHER", "region", "china", source="note")

    by_ticker = {r.ticker: r for r in screener.build_rows()}
    assert set(by_ticker) == {"DEMO", "OTHER"}
    assert by_ticker["DEMO"].attributes["region"].value == "us"
    assert by_ticker["OTHER"].attributes["region"].value == "china"


def test_empty_db(screener: ScreenerService) -> None:
    assert screener.build_rows() == []


def test_columns_exposes_definitions(
    screener: ScreenerService,
    attributes: AttributeService,
    company_repo: SQLiteCompanyRepo,
    demo_fin: CompanyFinancials,
) -> None:
    company_repo.save(demo_fin)
    attributes.set_value("DEMO", "region", "china", source="note")
    assert [d.key for d in screener.columns()] == ["region"]
