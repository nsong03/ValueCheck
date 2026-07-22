"""Note + tag repository round-trips, and the Phase 3 acceptance flow."""

from __future__ import annotations

import pytest

from equity.adapters.persistence.sqlite import (
    SQLiteCompanyRepo,
    SQLiteNoteRepo,
    SQLiteTagRepo,
    SQLiteValuationRepo,
)
from equity.domain.dcf import DCF
from equity.domain.models import CompanyFinancials
from equity.domain.research import Note
from equity.errors import PersistenceError

pytestmark = pytest.mark.integration


class TestNoteRoundTrip:
    def test_save_assigns_identity_and_timestamps(self, note_repo: SQLiteNoteRepo) -> None:
        note = Note(ticker="DEMO", title="Thesis", body="Wide moat.", tags=["moat", "hardware"])
        stored = note_repo.save(note)

        assert stored.id is not None and stored.id >= 1
        assert stored.created_at is not None
        assert stored.updated_at is not None
        assert stored.tags == ["hardware", "moat"]  # stored sorted

    def test_get_round_trip(self, note_repo: SQLiteNoteRepo) -> None:
        stored = note_repo.save(Note(ticker="DEMO", title="T", body="B", tags=["x"]))
        assert stored.id is not None
        loaded = note_repo.get(stored.id)
        assert loaded is not None
        assert loaded.title == "T"
        assert loaded.body == "B"
        assert loaded.tags == ["x"]
        assert loaded.created_at == stored.created_at

    def test_update_replaces_tags_and_bumps_updated_at(self, note_repo: SQLiteNoteRepo) -> None:
        stored = note_repo.save(Note(ticker="DEMO", title="T", body="B", tags=["old"]))
        stored.title = "T2"
        stored.tags = ["new1", "new2"]
        updated = note_repo.save(stored)

        assert updated.id == stored.id
        assert updated.title == "T2"
        assert updated.tags == ["new1", "new2"]
        assert updated.created_at == stored.created_at
        assert updated.updated_at is not None and stored.updated_at is not None
        assert updated.updated_at >= stored.updated_at

    def test_update_missing_note_raises(self, note_repo: SQLiteNoteRepo) -> None:
        with pytest.raises(PersistenceError):
            note_repo.save(Note(ticker="D", title="x", body="", id=999))

    def test_list_for_newest_first(self, note_repo: SQLiteNoteRepo) -> None:
        a = note_repo.save(Note(ticker="DEMO", title="a", body=""))
        b = note_repo.save(Note(ticker="DEMO", title="b", body=""))
        note_repo.save(Note(ticker="OTHER", title="c", body=""))
        listed = note_repo.list_for("DEMO")
        assert [n.id for n in listed] == [b.id, a.id]

    def test_delete_removes_note(self, note_repo: SQLiteNoteRepo) -> None:
        stored = note_repo.save(Note(ticker="DEMO", title="T", body=""))
        assert stored.id is not None
        assert note_repo.delete(stored.id) is True
        assert note_repo.get(stored.id) is None
        assert note_repo.delete(stored.id) is False


class TestTags:
    def test_all_tags_distinct_sorted(
        self, note_repo: SQLiteNoteRepo, tag_repo: SQLiteTagRepo
    ) -> None:
        note_repo.save(Note(ticker="A", title="1", body="", tags=["beta", "alpha"]))
        note_repo.save(Note(ticker="B", title="2", body="", tags=["alpha", "gamma"]))
        assert tag_repo.all_tags() == ["alpha", "beta", "gamma"]

    def test_deleting_note_prunes_its_links(
        self, note_repo: SQLiteNoteRepo, tag_repo: SQLiteTagRepo
    ) -> None:
        keep = note_repo.save(Note(ticker="A", title="1", body="", tags=["shared"]))
        gone = note_repo.save(Note(ticker="A", title="2", body="", tags=["shared", "solo"]))
        assert gone.id is not None
        note_repo.delete(gone.id)
        # link table pruned by cascade -> orphaned "solo" no longer suggested
        assert tag_repo.all_tags() == ["shared"]
        assert keep.id is not None and note_repo.get(keep.id) is not None

    def test_no_tags_empty(self, tag_repo: SQLiteTagRepo) -> None:
        assert tag_repo.all_tags() == []


class TestPhase3Acceptance:
    """BUILD_SPEC Phase 3: round-trip a company + valuation + note + tags."""

    def test_full_round_trip(
        self,
        company_repo: SQLiteCompanyRepo,
        valuation_repo: SQLiteValuationRepo,
        note_repo: SQLiteNoteRepo,
        tag_repo: SQLiteTagRepo,
        demo_fin: CompanyFinancials,
    ) -> None:
        # company
        company_repo.save(demo_fin)
        loaded_fin = company_repo.get("DEMO")
        assert loaded_fin is not None

        # valuation computed FROM the loaded company (full persistence cycle)
        result = DCF(loaded_fin).value()
        record = valuation_repo.save(result)
        loaded_val = valuation_repo.get(record.id)
        assert loaded_val is not None
        assert loaded_val.fair_value_per_share == result.fair_value_per_share

        # note + tags
        note = note_repo.save(
            Note(
                ticker="DEMO",
                title="Post-valuation thesis",
                body=f"Fair value {result.fair_value_per_share:.2f}",
                tags=["dcf", "thesis"],
            )
        )
        assert note.id is not None
        assert note_repo.list_for("DEMO")[0].id == note.id
        assert tag_repo.all_tags() == ["dcf", "thesis"]

        # sources survived the whole trip (audit trail intact)
        assert len(loaded_fin.sources) == 5
