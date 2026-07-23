"""Reference repository round-trips: the knowledge library (Phase 9b)."""

from __future__ import annotations

import pytest

from equity.adapters.persistence.sqlite import SQLiteReferenceRepo
from equity.domain.references import Reference
from equity.errors import PersistenceError

pytestmark = pytest.mark.integration


class TestReferenceRoundTrip:
    def test_save_assigns_identity_and_added_at(self, reference_repo: SQLiteReferenceRepo) -> None:
        stored = reference_repo.save(
            Reference(kind="pdf", title="Damodaran on Moats", location="C:/refs/moats.pdf")
        )
        assert stored.id is not None
        assert stored.added_at is not None
        assert stored.origin == "manual"  # dataclass default

    def test_get_round_trip(self, reference_repo: SQLiteReferenceRepo) -> None:
        stored = reference_repo.save(
            Reference(
                kind="webpage",
                title="Article",
                location="https://example.com/a",
                collection="Newsletters",
            )
        )
        assert stored.id is not None
        loaded = reference_repo.get(stored.id)
        assert loaded == stored

    def test_get_missing_returns_none(self, reference_repo: SQLiteReferenceRepo) -> None:
        assert reference_repo.get(999) is None

    def test_get_by_location(self, reference_repo: SQLiteReferenceRepo) -> None:
        reference_repo.save(Reference(kind="pdf", title="A", location="C:/refs/a.pdf"))
        found = reference_repo.get_by_location("C:/refs/a.pdf")
        assert found is not None
        assert found.title == "A"
        assert reference_repo.get_by_location("C:/refs/missing.pdf") is None

    def test_duplicate_location_raises(self, reference_repo: SQLiteReferenceRepo) -> None:
        reference_repo.save(Reference(kind="pdf", title="A", location="C:/refs/a.pdf"))
        with pytest.raises(PersistenceError):
            reference_repo.save(Reference(kind="pdf", title="A again", location="C:/refs/a.pdf"))

    def test_update_preserves_identity(self, reference_repo: SQLiteReferenceRepo) -> None:
        stored = reference_repo.save(Reference(kind="pdf", title="A", location="C:/refs/a.pdf"))
        assert stored.id is not None
        stored.title = "A Revised"
        stored.collection = "Valuation"
        updated = reference_repo.save(stored)
        assert updated.id == stored.id
        assert updated.title == "A Revised"
        assert updated.collection == "Valuation"

    def test_list_all_ordered_by_collection_then_title(
        self, reference_repo: SQLiteReferenceRepo
    ) -> None:
        reference_repo.save(
            Reference(kind="pdf", title="Zeta", location="C:/z.pdf", collection="A")
        )
        reference_repo.save(
            Reference(kind="pdf", title="Alpha", location="C:/a.pdf", collection="A")
        )
        reference_repo.save(
            Reference(kind="pdf", title="Beta", location="C:/b.pdf", collection="B")
        )
        listed = reference_repo.list_all()
        assert [(r.collection, r.title) for r in listed] == [
            ("A", "Alpha"),
            ("A", "Zeta"),
            ("B", "Beta"),
        ]

    def test_delete(self, reference_repo: SQLiteReferenceRepo) -> None:
        stored = reference_repo.save(Reference(kind="pdf", title="A", location="C:/a.pdf"))
        assert stored.id is not None
        assert reference_repo.delete(stored.id) is True
        assert reference_repo.get(stored.id) is None
        assert reference_repo.delete(stored.id) is False
