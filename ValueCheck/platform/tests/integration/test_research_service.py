"""Research service: canonicalization invariants, CRUD, and tag merge.

Notes attach to a company OR a reference (Phase 9b) — both paths share this
one service/vocabulary, so canonicalization/merge tests don't distinguish
between them except where the subject itself is what's under test.
"""

from __future__ import annotations

import pytest

from equity.adapters.persistence.sqlite import (
    SQLiteAnalysisRepo,
    SQLiteNoteRepo,
    SQLiteReferenceRepo,
    SQLiteTagRepo,
)
from equity.application.research_service import (
    ResearchService,
    canonicalize_tag,
    canonicalize_tags,
)
from equity.domain.analysis import Analysis
from equity.domain.references import Reference
from equity.domain.research import NoteLink
from equity.errors import NotFoundError, ValidationError

pytestmark = pytest.mark.integration


@pytest.fixture
def research(note_repo: SQLiteNoteRepo, tag_repo: SQLiteTagRepo) -> ResearchService:
    return ResearchService(note_repo, tag_repo)


def _make_reference(repo: SQLiteReferenceRepo, title: str = "A Book") -> int:
    stored = repo.save(Reference(kind="book", title=title, location=f"https://example.com/{title}"))
    assert stored.id is not None
    return stored.id


def _make_analysis(repo: SQLiteAnalysisRepo, title: str = "A Model") -> int:
    stored = repo.save(Analysis(kind="portfolio", title=title))
    assert stored.id is not None
    return stored.id


class TestCanonicalization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("  Wide Moat ", "wide-moat"),
            ("wide_moat", "wide-moat"),
            ("WIDE-MOAT", "wide-moat"),
            ("AI/ML", "ai-ml"),
            ("semis  &  chips", "semis-chips"),
            ("--edge--", "edge"),
            ("", ""),
            ("   ", ""),
            ("!!!", ""),
        ],
    )
    def test_canonicalize_tag(self, raw: str, expected: str) -> None:
        assert canonicalize_tag(raw) == expected

    def test_canonicalize_tags_dedupes_preserving_order(self) -> None:
        assert canonicalize_tags(["Wide Moat", "hardware", "wide-moat", "", "WIDE_MOAT"]) == [
            "wide-moat",
            "hardware",
        ]

    def test_variant_spellings_stored_as_one_tag(self, research: ResearchService) -> None:
        research.create_note(ticker="DEMO", title="a", body="", tags=["Wide Moat"])
        research.create_note(ticker="DEMO", title="b", body="", tags=["wide_moat"])
        research.create_note(ticker="DEMO", title="c", body="", tags=["wide-moat"])
        assert research.list_tags() == ["wide-moat"]


class TestNoteCrud:
    def test_create_get_roundtrip(self, research: ResearchService) -> None:
        created = research.create_note(
            ticker="demo", title="  Thesis  ", body="Body.", tags=["Moat", "AI/ML"]
        )
        assert created.id is not None
        assert created.ticker == "DEMO"  # normalized
        assert created.reference_id is None
        assert created.title == "Thesis"  # trimmed
        assert created.tags == ["ai-ml", "moat"]  # canonical, sorted by repo

        loaded = research.get_note(created.id)
        assert loaded.body == "Body."
        assert loaded.tags == ["ai-ml", "moat"]

    def test_update_recanonicalizes(self, research: ResearchService) -> None:
        note = research.create_note(ticker="DEMO", title="t", body="", tags=["old"])
        assert note.id is not None
        updated = research.update_note(note.id, title="t2", body="b2", tags=["New Tag"])
        assert updated.title == "t2"
        assert updated.tags == ["new-tag"]
        assert research.list_tags() == ["new-tag"]  # old orphan pruned from vocab

    def test_update_does_not_change_the_subject(self, research: ResearchService) -> None:
        note = research.create_note(ticker="DEMO", title="t", body="", tags=[])
        assert note.id is not None
        updated = research.update_note(note.id, title="t2", body="", tags=[])
        assert updated.ticker == "DEMO"
        assert updated.reference_id is None

    def test_list_notes_scoped_and_ordered(self, research: ResearchService) -> None:
        a = research.create_note(ticker="DEMO", title="a", body="", tags=[])
        b = research.create_note(ticker="DEMO", title="b", body="", tags=[])
        research.create_note(ticker="OTHER", title="x", body="", tags=[])
        assert [n.id for n in research.list_notes("demo")] == [b.id, a.id]

    def test_missing_note_raises_not_found(self, research: ResearchService) -> None:
        with pytest.raises(NotFoundError):
            research.get_note(999)
        with pytest.raises(NotFoundError):
            research.update_note(999, title="x", body="", tags=[])
        with pytest.raises(NotFoundError):
            research.delete_note(999)

    def test_blank_title_rejected(self, research: ResearchService) -> None:
        with pytest.raises(ValidationError):
            research.create_note(ticker="DEMO", title="   ", body="", tags=[])


class TestSubjectValidation:
    def test_neither_ticker_nor_reference_rejected(self, research: ResearchService) -> None:
        with pytest.raises(ValidationError):
            research.create_note(title="t", body="", tags=[])

    def test_both_ticker_and_reference_rejected(
        self, research: ResearchService, reference_repo: SQLiteReferenceRepo
    ) -> None:
        ref_id = _make_reference(reference_repo)
        with pytest.raises(ValidationError):
            research.create_note(ticker="DEMO", reference_id=ref_id, title="t", body="", tags=[])

    def test_reference_only_note(
        self, research: ResearchService, reference_repo: SQLiteReferenceRepo
    ) -> None:
        ref_id = _make_reference(reference_repo)
        note = research.create_note(
            reference_id=ref_id, title="Chapter 3 thoughts", body="", tags=[]
        )
        assert note.ticker is None
        assert note.reference_id == ref_id

    def test_list_notes_for_reference_scoped_and_ordered(
        self, research: ResearchService, reference_repo: SQLiteReferenceRepo
    ) -> None:
        ref1 = _make_reference(reference_repo, "Book One")
        ref2 = _make_reference(reference_repo, "Book Two")
        a = research.create_note(reference_id=ref1, title="a", body="", tags=[])
        b = research.create_note(reference_id=ref1, title="b", body="", tags=[])
        research.create_note(reference_id=ref2, title="x", body="", tags=[])
        assert [n.id for n in research.list_notes_for_reference(ref1)] == [b.id, a.id]

    def test_all_three_subjects_rejected(
        self,
        research: ResearchService,
        reference_repo: SQLiteReferenceRepo,
        analysis_repo: SQLiteAnalysisRepo,
    ) -> None:
        ref_id = _make_reference(reference_repo)
        an_id = _make_analysis(analysis_repo)
        with pytest.raises(ValidationError):
            research.create_note(
                ticker="DEMO",
                reference_id=ref_id,
                analysis_id=an_id,
                title="t",
                body="",
                tags=[],
            )

    def test_ticker_and_analysis_rejected(
        self, research: ResearchService, analysis_repo: SQLiteAnalysisRepo
    ) -> None:
        an_id = _make_analysis(analysis_repo)
        with pytest.raises(ValidationError):
            research.create_note(ticker="DEMO", analysis_id=an_id, title="t", body="", tags=[])

    def test_analysis_only_note(
        self, research: ResearchService, analysis_repo: SQLiteAnalysisRepo
    ) -> None:
        an_id = _make_analysis(analysis_repo)
        note = research.create_note(analysis_id=an_id, title="Model notes", body="", tags=[])
        assert note.ticker is None
        assert note.reference_id is None
        assert note.analysis_id == an_id

    def test_list_notes_for_analysis_scoped_and_ordered(
        self, research: ResearchService, analysis_repo: SQLiteAnalysisRepo
    ) -> None:
        an1 = _make_analysis(analysis_repo, "Model One")
        an2 = _make_analysis(analysis_repo, "Model Two")
        a = research.create_note(analysis_id=an1, title="a", body="", tags=[])
        b = research.create_note(analysis_id=an1, title="b", body="", tags=[])
        research.create_note(analysis_id=an2, title="x", body="", tags=[])
        assert [n.id for n in research.list_notes_for_analysis(an1)] == [b.id, a.id]


class TestLinks:
    def test_links_round_trip(self, research: ResearchService) -> None:
        links = [NoteLink(label="Damodaran on WACC", url="https://example.com/wacc")]
        created = research.create_note(ticker="DEMO", title="t", body="", tags=[], links=links)
        assert created.id is not None
        loaded = research.get_note(created.id)
        assert loaded.links == links

    def test_update_replaces_links(self, research: ResearchService) -> None:
        note = research.create_note(
            ticker="DEMO",
            title="t",
            body="",
            tags=[],
            links=[NoteLink(label="old", url="https://old.example")],
        )
        assert note.id is not None
        updated = research.update_note(
            note.id,
            title="t",
            body="",
            tags=[],
            links=[NoteLink(label="new", url="https://new.example")],
        )
        assert updated.links == [NoteLink(label="new", url="https://new.example")]

    def test_no_links_defaults_empty(self, research: ResearchService) -> None:
        note = research.create_note(ticker="DEMO", title="t", body="", tags=[])
        assert note.links == []


class TestTagMerge:
    def test_merge_folds_source_into_target(self, research: ResearchService) -> None:
        n1 = research.create_note(ticker="A", title="1", body="", tags=["semis", "hardware"])
        n2 = research.create_note(ticker="B", title="2", body="", tags=["semis"])
        n3 = research.create_note(ticker="C", title="3", body="", tags=["semiconductors"])

        affected = research.merge_tags("semis", "semiconductors")

        assert affected == 2
        assert research.list_tags() == ["hardware", "semiconductors"]
        assert n1.id is not None and n2.id is not None and n3.id is not None
        assert research.get_note(n1.id).tags == ["hardware", "semiconductors"]
        assert research.get_note(n2.id).tags == ["semiconductors"]
        assert research.get_note(n3.id).tags == ["semiconductors"]

    def test_merge_canonicalizes_inputs(self, research: ResearchService) -> None:
        research.create_note(ticker="A", title="1", body="", tags=["wide-moat"])
        affected = research.merge_tags("Wide Moat", "MOAT")
        assert affected == 1
        assert research.list_tags() == ["moat"]

    def test_merge_when_note_has_both_tags(self, research: ResearchService) -> None:
        note = research.create_note(
            ticker="A", title="1", body="", tags=["semis", "semiconductors"]
        )
        affected = research.merge_tags("semis", "semiconductors")
        assert affected == 1
        assert note.id is not None
        assert research.get_note(note.id).tags == ["semiconductors"]  # no dup

    def test_merge_unknown_source_is_noop(self, research: ResearchService) -> None:
        research.create_note(ticker="A", title="1", body="", tags=["kept"])
        assert research.merge_tags("ghost", "kept") == 0
        assert research.list_tags() == ["kept"]

    def test_merge_same_canonical_rejected(self, research: ResearchService) -> None:
        with pytest.raises(ValidationError):
            research.merge_tags("Wide Moat", "wide-moat")
