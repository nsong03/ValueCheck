"""Research service: canonicalization invariants, CRUD, and tag merge."""

from __future__ import annotations

import pytest

from equity.adapters.persistence.sqlite import SQLiteNoteRepo, SQLiteTagRepo
from equity.application.research_service import (
    ResearchService,
    canonicalize_tag,
    canonicalize_tags,
)
from equity.errors import NotFoundError, ValidationError

pytestmark = pytest.mark.integration


@pytest.fixture
def research(note_repo: SQLiteNoteRepo, tag_repo: SQLiteTagRepo) -> ResearchService:
    return ResearchService(note_repo, tag_repo)


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
        research.create_note("DEMO", "a", "", ["Wide Moat"])
        research.create_note("DEMO", "b", "", ["wide_moat"])
        research.create_note("DEMO", "c", "", ["wide-moat"])
        assert research.list_tags() == ["wide-moat"]


class TestNoteCrud:
    def test_create_get_roundtrip(self, research: ResearchService) -> None:
        created = research.create_note("demo", "  Thesis  ", "Body.", ["Moat", "AI/ML"])
        assert created.id is not None
        assert created.ticker == "DEMO"  # normalized
        assert created.title == "Thesis"  # trimmed
        assert created.tags == ["ai-ml", "moat"]  # canonical, sorted by repo

        loaded = research.get_note(created.id)
        assert loaded.body == "Body."
        assert loaded.tags == ["ai-ml", "moat"]

    def test_update_recanonicalizes(self, research: ResearchService) -> None:
        note = research.create_note("DEMO", "t", "", ["old"])
        assert note.id is not None
        updated = research.update_note(note.id, title="t2", body="b2", tags=["New Tag"])
        assert updated.title == "t2"
        assert updated.tags == ["new-tag"]
        assert research.list_tags() == ["new-tag"]  # old orphan pruned from vocab

    def test_list_notes_scoped_and_ordered(self, research: ResearchService) -> None:
        a = research.create_note("DEMO", "a", "", [])
        b = research.create_note("DEMO", "b", "", [])
        research.create_note("OTHER", "x", "", [])
        assert [n.id for n in research.list_notes("demo")] == [b.id, a.id]

    def test_missing_note_raises_not_found(self, research: ResearchService) -> None:
        with pytest.raises(NotFoundError):
            research.get_note(999)
        with pytest.raises(NotFoundError):
            research.update_note(999, title="x", body="", tags=[])
        with pytest.raises(NotFoundError):
            research.delete_note(999)

    def test_validation(self, research: ResearchService) -> None:
        with pytest.raises(ValidationError):
            research.create_note("DEMO", "   ", "", [])


class TestTagMerge:
    def test_merge_folds_source_into_target(self, research: ResearchService) -> None:
        n1 = research.create_note("A", "1", "", ["semis", "hardware"])
        n2 = research.create_note("B", "2", "", ["semis"])
        n3 = research.create_note("C", "3", "", ["semiconductors"])

        affected = research.merge_tags("semis", "semiconductors")

        assert affected == 2
        assert research.list_tags() == ["hardware", "semiconductors"]
        assert n1.id is not None and n2.id is not None and n3.id is not None
        assert research.get_note(n1.id).tags == ["hardware", "semiconductors"]
        assert research.get_note(n2.id).tags == ["semiconductors"]
        assert research.get_note(n3.id).tags == ["semiconductors"]

    def test_merge_canonicalizes_inputs(self, research: ResearchService) -> None:
        research.create_note("A", "1", "", ["wide-moat"])
        affected = research.merge_tags("Wide Moat", "MOAT")
        assert affected == 1
        assert research.list_tags() == ["moat"]

    def test_merge_when_note_has_both_tags(self, research: ResearchService) -> None:
        note = research.create_note("A", "1", "", ["semis", "semiconductors"])
        affected = research.merge_tags("semis", "semiconductors")
        assert affected == 1
        assert note.id is not None
        assert research.get_note(note.id).tags == ["semiconductors"]  # no dup

    def test_merge_unknown_source_is_noop(self, research: ResearchService) -> None:
        research.create_note("A", "1", "", ["kept"])
        assert research.merge_tags("ghost", "kept") == 0
        assert research.list_tags() == ["kept"]

    def test_merge_same_canonical_rejected(self, research: ResearchService) -> None:
        with pytest.raises(ValidationError):
            research.merge_tags("Wide Moat", "wide-moat")
