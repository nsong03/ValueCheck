"""Analysis service: CRUD validation, and explicit constituent management
(the balcony, Phase 9c)."""

from __future__ import annotations

import pytest

from equity.adapters.persistence.sqlite import SQLiteAnalysisRepo, SQLiteReferenceRepo
from equity.application.analysis_service import AnalysisService
from equity.domain.references import Reference
from equity.errors import NotFoundError, ValidationError

pytestmark = pytest.mark.integration


@pytest.fixture
def analyses(analysis_repo: SQLiteAnalysisRepo) -> AnalysisService:
    return AnalysisService(analysis_repo)


def _make_reference(repo: SQLiteReferenceRepo, location: str = "https://example.com/r") -> int:
    stored = repo.save(Reference(kind="pdf", title="R", location=location))
    assert stored.id is not None
    return stored.id


class TestCrud:
    def test_create_get_roundtrip(self, analyses: AnalysisService) -> None:
        created = analyses.create(kind="  Portfolio  ", title="  Core holdings  ", summary="s")
        assert created.id is not None
        assert created.kind == "Portfolio"  # trimmed, not canonicalized (free text)
        assert created.title == "Core holdings"

        loaded = analyses.get(created.id)
        assert loaded.summary == "s"

    def test_blank_kind_or_title_rejected(self, analyses: AnalysisService) -> None:
        with pytest.raises(ValidationError):
            analyses.create(kind="", title="x")
        with pytest.raises(ValidationError):
            analyses.create(kind="portfolio", title="")

    def test_get_missing_raises_not_found(self, analyses: AnalysisService) -> None:
        with pytest.raises(NotFoundError):
            analyses.get(999)

    def test_update_partial(self, analyses: AnalysisService) -> None:
        created = analyses.create(kind="portfolio", title="A")
        assert created.id is not None
        updated = analyses.update(created.id, title="A Revised")
        assert updated.title == "A Revised"
        assert updated.kind == "portfolio"  # untouched

    def test_update_missing_raises_not_found(self, analyses: AnalysisService) -> None:
        with pytest.raises(NotFoundError):
            analyses.update(999, title="x")

    def test_delete_missing_raises_not_found(self, analyses: AnalysisService) -> None:
        with pytest.raises(NotFoundError):
            analyses.delete(999)

    def test_list_all(self, analyses: AnalysisService) -> None:
        analyses.create(kind="portfolio", title="A")
        analyses.create(kind="other", title="B")
        assert {a.title for a in analyses.list_all()} == {"A", "B"}


class TestCompanyConstituents:
    def test_add_normalizes_ticker(self, analyses: AnalysisService) -> None:
        created = analyses.create(kind="correlation-study", title="Semis")
        assert created.id is not None
        analyses.add_company(created.id, "  tsm ")
        assert analyses.companies(created.id) == ["TSM"]

    def test_add_blank_ticker_rejected(self, analyses: AnalysisService) -> None:
        created = analyses.create(kind="portfolio", title="p")
        assert created.id is not None
        with pytest.raises(ValidationError):
            analyses.add_company(created.id, "   ")

    def test_add_to_missing_analysis_raises_not_found(self, analyses: AnalysisService) -> None:
        with pytest.raises(NotFoundError):
            analyses.add_company(999, "AAPL")

    def test_reverse_lookup(self, analyses: AnalysisService) -> None:
        a = analyses.create(kind="portfolio", title="A")
        b = analyses.create(kind="correlation-study", title="B")
        assert a.id is not None and b.id is not None
        analyses.add_company(a.id, "AAPL")
        analyses.add_company(b.id, "aapl")  # same ticker, different case
        assert {x.id for x in analyses.analyses_for_company("AAPL")} == {a.id, b.id}


class TestReferenceConstituents:
    def test_add_list_remove(
        self, analyses: AnalysisService, reference_repo: SQLiteReferenceRepo
    ) -> None:
        ref_id = _make_reference(reference_repo)
        created = analyses.create(kind="dcf-variant", title="Model")
        assert created.id is not None
        analyses.add_reference(created.id, ref_id)
        assert analyses.references(created.id) == [ref_id]
        analyses.remove_reference(created.id, ref_id)
        assert analyses.references(created.id) == []

    def test_add_to_missing_analysis_raises_not_found(self, analyses: AnalysisService) -> None:
        with pytest.raises(NotFoundError):
            analyses.add_reference(999, 1)


class TestAnalysisLinks:
    def test_self_link_rejected(self, analyses: AnalysisService) -> None:
        created = analyses.create(kind="portfolio", title="A")
        assert created.id is not None
        with pytest.raises(ValidationError):
            analyses.add_link(created.id, created.id)

    def test_link_to_missing_analysis_raises_not_found(self, analyses: AnalysisService) -> None:
        created = analyses.create(kind="portfolio", title="A")
        assert created.id is not None
        with pytest.raises(NotFoundError):
            analyses.add_link(created.id, 999)

    def test_add_list_remove(self, analyses: AnalysisService) -> None:
        a = analyses.create(kind="correlation-study", title="A")
        b = analyses.create(kind="portfolio", title="B")
        assert a.id is not None and b.id is not None
        analyses.add_link(a.id, b.id)
        assert analyses.links(a.id) == [b.id]
        analyses.remove_link(a.id, b.id)
        assert analyses.links(a.id) == []
