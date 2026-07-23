"""Analysis repository round-trips: the balcony (Phase 9c) — CRUD, and its
EXPLICIT links to companies, references, and other analyses."""

from __future__ import annotations

import pytest

from equity.adapters.persistence.sqlite import SQLiteAnalysisRepo, SQLiteReferenceRepo
from equity.domain.analysis import Analysis
from equity.domain.references import Reference
from equity.errors import PersistenceError

pytestmark = pytest.mark.integration


class TestAnalysisRoundTrip:
    def test_save_assigns_identity_and_timestamps(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        stored = analysis_repo.save(
            Analysis(kind="correlation-study", title="Semis vs. rates", summary="Draft")
        )
        assert stored.id is not None
        assert stored.created_at is not None
        assert stored.updated_at is not None

    def test_get_round_trip(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        stored = analysis_repo.save(Analysis(kind="portfolio", title="Core holdings"))
        assert stored.id is not None
        loaded = analysis_repo.get(stored.id)
        assert loaded == stored

    def test_get_missing_returns_none(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        assert analysis_repo.get(999) is None

    def test_update_preserves_created_at_bumps_updated_at(
        self, analysis_repo: SQLiteAnalysisRepo
    ) -> None:
        stored = analysis_repo.save(Analysis(kind="portfolio", title="Core"))
        stored.title = "Core Revised"
        updated = analysis_repo.save(stored)
        assert updated.id == stored.id
        assert updated.title == "Core Revised"
        assert updated.created_at == stored.created_at
        assert updated.updated_at >= stored.updated_at

    def test_update_missing_raises(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        with pytest.raises(PersistenceError):
            analysis_repo.save(Analysis(kind="portfolio", title="x", id=999))

    def test_list_all_newest_first(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        a = analysis_repo.save(Analysis(kind="other", title="a"))
        b = analysis_repo.save(Analysis(kind="other", title="b"))
        assert [x.id for x in analysis_repo.list_all()] == [b.id, a.id]

    def test_delete(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        stored = analysis_repo.save(Analysis(kind="other", title="x"))
        assert stored.id is not None
        assert analysis_repo.delete(stored.id) is True
        assert analysis_repo.get(stored.id) is None
        assert analysis_repo.delete(stored.id) is False


class TestCompanyConstituents:
    def test_add_list_remove(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        stored = analysis_repo.save(Analysis(kind="correlation-study", title="Semis"))
        assert stored.id is not None
        analysis_repo.add_company(stored.id, "TSM")
        analysis_repo.add_company(stored.id, "AAPL")
        assert analysis_repo.list_companies(stored.id) == ["AAPL", "TSM"]

        analysis_repo.remove_company(stored.id, "AAPL")
        assert analysis_repo.list_companies(stored.id) == ["TSM"]

    def test_add_is_idempotent(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        stored = analysis_repo.save(Analysis(kind="portfolio", title="p"))
        assert stored.id is not None
        analysis_repo.add_company(stored.id, "AAPL")
        analysis_repo.add_company(stored.id, "AAPL")
        assert analysis_repo.list_companies(stored.id) == ["AAPL"]

    def test_list_for_company_reverse_lookup(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        a = analysis_repo.save(Analysis(kind="portfolio", title="A"))
        b = analysis_repo.save(Analysis(kind="correlation-study", title="B"))
        assert a.id is not None and b.id is not None
        analysis_repo.add_company(a.id, "AAPL")
        analysis_repo.add_company(b.id, "AAPL")
        analysis_repo.add_company(b.id, "TSM")

        touching_aapl = analysis_repo.list_for_company("AAPL")
        assert {x.id for x in touching_aapl} == {a.id, b.id}
        assert {x.id for x in analysis_repo.list_for_company("TSM")} == {b.id}
        assert analysis_repo.list_for_company("GHOST") == []

    def test_deleting_analysis_cascades_company_links(
        self, analysis_repo: SQLiteAnalysisRepo
    ) -> None:
        stored = analysis_repo.save(Analysis(kind="portfolio", title="p"))
        assert stored.id is not None
        analysis_repo.add_company(stored.id, "AAPL")
        analysis_repo.delete(stored.id)
        assert analysis_repo.list_for_company("AAPL") == []


class TestReferenceConstituents:
    @pytest.fixture
    def ref_id(self, reference_repo: SQLiteReferenceRepo) -> int:
        stored = reference_repo.save(
            Reference(kind="book", title="A Book", location="https://example.com/book")
        )
        assert stored.id is not None
        return stored.id

    def test_add_list_remove(self, analysis_repo: SQLiteAnalysisRepo, ref_id: int) -> None:
        stored = analysis_repo.save(Analysis(kind="dcf-variant", title="Model"))
        assert stored.id is not None
        analysis_repo.add_reference(stored.id, ref_id)
        assert analysis_repo.list_references(stored.id) == [ref_id]
        analysis_repo.remove_reference(stored.id, ref_id)
        assert analysis_repo.list_references(stored.id) == []

    def test_list_for_reference_reverse_lookup(
        self, analysis_repo: SQLiteAnalysisRepo, ref_id: int
    ) -> None:
        a = analysis_repo.save(Analysis(kind="dcf-variant", title="A"))
        b = analysis_repo.save(Analysis(kind="portfolio", title="B"))
        assert a.id is not None and b.id is not None
        analysis_repo.add_reference(a.id, ref_id)
        analysis_repo.add_reference(b.id, ref_id)
        assert {x.id for x in analysis_repo.list_for_reference(ref_id)} == {a.id, b.id}

    def test_add_unknown_reference_raises(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        stored = analysis_repo.save(Analysis(kind="portfolio", title="p"))
        assert stored.id is not None
        with pytest.raises(PersistenceError):
            analysis_repo.add_reference(stored.id, 999)

    def test_deleting_reference_prunes_the_link(
        self, analysis_repo: SQLiteAnalysisRepo, reference_repo: SQLiteReferenceRepo, ref_id: int
    ) -> None:
        stored = analysis_repo.save(Analysis(kind="portfolio", title="p"))
        assert stored.id is not None
        analysis_repo.add_reference(stored.id, ref_id)
        reference_repo.delete(ref_id)
        assert analysis_repo.list_references(stored.id) == []


class TestAnalysisLinks:
    def test_add_list_remove(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        a = analysis_repo.save(Analysis(kind="correlation-study", title="A"))
        b = analysis_repo.save(Analysis(kind="portfolio", title="B"))
        assert a.id is not None and b.id is not None
        analysis_repo.add_link(a.id, b.id)
        assert analysis_repo.list_links(a.id) == [b.id]
        assert analysis_repo.list_links(b.id) == []  # directed: B does not link back

        analysis_repo.remove_link(a.id, b.id)
        assert analysis_repo.list_links(a.id) == []

    def test_add_is_idempotent(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        a = analysis_repo.save(Analysis(kind="other", title="A"))
        b = analysis_repo.save(Analysis(kind="other", title="B"))
        assert a.id is not None and b.id is not None
        analysis_repo.add_link(a.id, b.id)
        analysis_repo.add_link(a.id, b.id)
        assert analysis_repo.list_links(a.id) == [b.id]

    def test_deleting_either_side_prunes_the_link(self, analysis_repo: SQLiteAnalysisRepo) -> None:
        a = analysis_repo.save(Analysis(kind="other", title="A"))
        b = analysis_repo.save(Analysis(kind="other", title="B"))
        assert a.id is not None and b.id is not None
        analysis_repo.add_link(a.id, b.id)
        analysis_repo.delete(b.id)
        assert analysis_repo.list_links(a.id) == []
