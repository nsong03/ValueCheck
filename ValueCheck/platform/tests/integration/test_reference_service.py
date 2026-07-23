"""Reference service: manual CRUD, and the on-demand library scan that
stands in for a persistent file watcher (BUILD_SPEC rules out a background
task queue for v1 — see equity.application.reference_service module docs)."""

from __future__ import annotations

from pathlib import Path

import pytest

from equity.adapters.persistence.sqlite import SQLiteReferenceRepo
from equity.application.reference_service import ReferenceService
from equity.errors import ConflictError, NotFoundError, ValidationError

pytestmark = pytest.mark.integration


@pytest.fixture
def references(reference_repo: SQLiteReferenceRepo) -> ReferenceService:
    return ReferenceService(reference_repo)


class TestCreate:
    def test_create_manual_reference(self, references: ReferenceService) -> None:
        ref = references.create(
            kind="webpage", title="An Article", location="https://example.com/a"
        )
        assert ref.id is not None
        assert ref.origin == "manual"
        assert ref.collection == ""

    def test_duplicate_location_raises_conflict(self, references: ReferenceService) -> None:
        references.create(kind="pdf", title="A", location="C:/refs/a.pdf")
        with pytest.raises(ConflictError):
            references.create(kind="pdf", title="A again", location="C:/refs/a.pdf")

    def test_blank_fields_rejected(self, references: ReferenceService) -> None:
        with pytest.raises(ValidationError):
            references.create(kind="", title="A", location="C:/a.pdf")
        with pytest.raises(ValidationError):
            references.create(kind="pdf", title="", location="C:/a.pdf")
        with pytest.raises(ValidationError):
            references.create(kind="pdf", title="A", location="")

    def test_manual_local_path_under_library_auto_derives_collection(
        self, reference_repo: SQLiteReferenceRepo, tmp_path: Path
    ) -> None:
        root = tmp_path / "TechnicalReading"
        (root / "Valuation").mkdir(parents=True)
        file_path = root / "Valuation" / "book.pdf"
        file_path.write_bytes(b"%PDF-1.4")

        service = ReferenceService(reference_repo, library_path=root)
        ref = service.create(kind="pdf", title="Book", location=str(file_path))
        assert ref.collection == "Valuation"

    def test_explicit_collection_wins_over_derivation(
        self, reference_repo: SQLiteReferenceRepo, tmp_path: Path
    ) -> None:
        root = tmp_path / "TechnicalReading"
        (root / "Valuation").mkdir(parents=True)
        file_path = root / "Valuation" / "book.pdf"
        file_path.write_bytes(b"%PDF-1.4")

        service = ReferenceService(reference_repo, library_path=root)
        ref = service.create(
            kind="pdf", title="Book", location=str(file_path), collection="My Own Label"
        )
        assert ref.collection == "My Own Label"


class TestGetUpdateDelete:
    def test_get_missing_raises_not_found(self, references: ReferenceService) -> None:
        with pytest.raises(NotFoundError):
            references.get(999)

    def test_update_partial_fields(self, references: ReferenceService) -> None:
        ref = references.create(kind="pdf", title="A", location="C:/a.pdf")
        assert ref.id is not None
        updated = references.update(ref.id, title="A Revised")
        assert updated.title == "A Revised"
        assert updated.kind == "pdf"  # untouched

    def test_update_missing_raises_not_found(self, references: ReferenceService) -> None:
        with pytest.raises(NotFoundError):
            references.update(999, title="x")

    def test_delete_missing_raises_not_found(self, references: ReferenceService) -> None:
        with pytest.raises(NotFoundError):
            references.delete(999)

    def test_list_all(self, references: ReferenceService) -> None:
        references.create(kind="pdf", title="A", location="C:/a.pdf")
        references.create(kind="pdf", title="B", location="C:/b.pdf")
        assert {r.title for r in references.list_all()} == {"A", "B"}


class TestScan:
    def test_no_library_path_configured_is_a_noop(
        self, reference_repo: SQLiteReferenceRepo
    ) -> None:
        service = ReferenceService(reference_repo, library_path=None)
        assert service.scan() == []

    def test_missing_directory_is_a_noop_not_an_error(
        self, reference_repo: SQLiteReferenceRepo, tmp_path: Path
    ) -> None:
        service = ReferenceService(reference_repo, library_path=tmp_path / "does-not-exist")
        assert service.scan() == []

    def test_scan_finds_pdfs_and_derives_nested_collections(
        self, reference_repo: SQLiteReferenceRepo, tmp_path: Path
    ) -> None:
        root = tmp_path / "TechnicalReading"
        (root / "Valuation").mkdir(parents=True)
        (root / "Quantum" / "Nested").mkdir(parents=True)
        (root / "top_level.pdf").write_bytes(b"%PDF-1.4")
        (root / "Valuation" / "damodaran_moats.pdf").write_bytes(b"%PDF-1.4")
        (root / "Quantum" / "Nested" / "nielsen.pdf").write_bytes(b"%PDF-1.4")
        (root / "Valuation" / "notes.txt").write_text("not a pdf")  # ignored

        service = ReferenceService(reference_repo, library_path=root)
        created = service.scan()

        by_title = {r.title: r for r in created}
        assert set(by_title) == {"top level", "damodaran moats", "nielsen"}
        assert by_title["damodaran moats"].collection == "Valuation"
        assert by_title["nielsen"].collection == "Quantum/Nested"
        assert by_title["top level"].collection == ""
        assert all(r.origin == "scan" for r in created)
        assert all(r.kind == "pdf" for r in created)

    def test_scan_is_idempotent(self, reference_repo: SQLiteReferenceRepo, tmp_path: Path) -> None:
        root = tmp_path / "TechnicalReading"
        root.mkdir()
        (root / "a.pdf").write_bytes(b"%PDF-1.4")

        service = ReferenceService(reference_repo, library_path=root)
        first = service.scan()
        second = service.scan()

        assert len(first) == 1
        assert second == []  # nothing new
        assert len(service.list_all()) == 1

    def test_scan_picks_up_files_added_after_a_previous_scan(
        self, reference_repo: SQLiteReferenceRepo, tmp_path: Path
    ) -> None:
        root = tmp_path / "TechnicalReading"
        root.mkdir()
        (root / "a.pdf").write_bytes(b"%PDF-1.4")

        service = ReferenceService(reference_repo, library_path=root)
        service.scan()
        (root / "b.pdf").write_bytes(b"%PDF-1.4")
        second = service.scan()

        assert [r.title for r in second] == ["b"]
        assert len(service.list_all()) == 2
