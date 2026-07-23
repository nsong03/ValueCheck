"""Reference service: the knowledge library — books, articles, PDFs, and
webpages that research notes can attach to (Phase 9b).

`scan()` is the on-demand alternative to a persistent file watcher: BUILD_SPEC
rules out a background task queue for v1, so new PDFs are picked up by
walking the configured folder now (triggered manually, or once at server
startup) rather than continuously. It is idempotent — re-running finds
nothing new for files it has already tracked (deduped by `location`).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from equity.domain.references import Reference
from equity.errors import ConflictError, NotFoundError, ValidationError
from equity.logging import get_logger
from equity.ports.repository import ReferenceRepo

log = get_logger(__name__)


def _collection_for(path: Path, root: Path) -> str:
    """The folder-derived collection for `path` relative to `root`, e.g.
    "TechnicalReading/Valuation" for a file two levels under `root`; "" for
    a file directly in `root`."""
    rel_dir = path.resolve().parent.relative_to(root.resolve())
    return "" if rel_dir == Path() else rel_dir.as_posix()


def _title_for(path: Path) -> str:
    """Humanized default title from a filename: 'damodaran_2023.pdf' ->
    'damodaran 2023'."""
    return path.stem.replace("_", " ").replace("-", " ").strip()


class ReferenceService:
    def __init__(self, references: ReferenceRepo, library_path: Path | None = None) -> None:
        self._references = references
        self._library_path = library_path

    def create(self, *, kind: str, title: str, location: str, collection: str = "") -> Reference:
        kind = kind.strip()
        title = title.strip()
        location = location.strip()
        if not kind or not title or not location:
            raise ValidationError("reference requires kind, title, and location")
        if self._references.get_by_location(location) is not None:
            raise ConflictError(f"a reference already points at {location!r}")

        if (
            not collection
            and self._library_path is not None
            and not location.startswith(("http://", "https://"))
        ):
            path = Path(location)
            with contextlib.suppress(ValueError):  # not under the configured library path
                collection = _collection_for(path, self._library_path)

        stored = self._references.save(
            Reference(kind=kind, title=title, location=location, collection=collection)
        )
        log.info("reference.created", reference_id=stored.id, kind=kind, origin="manual")
        return stored

    def get(self, reference_id: int) -> Reference:
        reference = self._references.get(reference_id)
        if reference is None:
            raise NotFoundError(f"reference {reference_id} not found")
        return reference

    def list_all(self) -> list[Reference]:
        return self._references.list_all()

    def update(
        self,
        reference_id: int,
        *,
        kind: str | None = None,
        title: str | None = None,
        collection: str | None = None,
    ) -> Reference:
        existing = self.get(reference_id)
        existing.kind = kind.strip() if kind is not None else existing.kind
        existing.title = title.strip() if title is not None else existing.title
        existing.collection = collection if collection is not None else existing.collection
        stored = self._references.save(existing)
        log.info("reference.updated", reference_id=reference_id)
        return stored

    def delete(self, reference_id: int) -> None:
        if not self._references.delete(reference_id):
            raise NotFoundError(f"reference {reference_id} not found")
        log.info("reference.deleted", reference_id=reference_id)

    def scan(self) -> list[Reference]:
        """Walk the configured library path for PDFs not yet tracked (by
        `location`), insert them, and return only the newly created ones.

        No-ops (returns []) when no library path is configured, rather than
        raising — this runs unconditionally at startup, and a misconfigured
        or absent folder shouldn't be an error there.
        """
        if self._library_path is None:
            return []
        root = self._library_path
        if not root.is_dir():
            log.warning("references.scan_skipped", path=str(root), reason="not a directory")
            return []

        created: list[Reference] = []
        for path in sorted(root.rglob("*.pdf")):
            location = str(path.resolve())
            if self._references.get_by_location(location) is not None:
                continue
            stored = self._references.save(
                Reference(
                    kind="pdf",
                    title=_title_for(path),
                    location=location,
                    collection=_collection_for(path, root),
                    origin="scan",
                )
            )
            created.append(stored)
        log.info("references.scanned", path=str(root), created=len(created))
        return created
