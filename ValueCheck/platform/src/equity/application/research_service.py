"""Research use-cases: notes CRUD and the tag vocabulary.

Tag canonicalization is a SERVER-side invariant (BUILD_SPEC Phase 7): every
tag is stored in canonical form no matter how the client spelled it, so
"Wide Moat", "wide_moat" and "wide-moat" are one tag. The client's fuzzy
suggest (fuse.js) only helps typing; it never defines identity.

A note attaches to a company, a reference (Phase 9b: the knowledge library),
or an analysis (Phase 9c: the balcony) — exactly one of `ticker`/
`reference_id`/`analysis_id` is required on creation and is immutable
afterward (updates only ever touch title/body/tags/links). All three kinds
share this one tag vocabulary, which is what lets a note on a book, a note
on a stock, and a note on a model end up connected in the research graph.
"""

from __future__ import annotations

import re

from equity.domain.research import Note, NoteLink
from equity.errors import NotFoundError, ValidationError
from equity.logging import get_logger
from equity.ports.repository import NoteRepo, TagRepo

log = get_logger(__name__)

_SEPARATORS = re.compile(r"[\s_/]+")
_DISALLOWED = re.compile(r"[^a-z0-9-]")
_HYPHEN_RUNS = re.compile(r"-{2,}")


def canonicalize_tag(raw: str) -> str:
    """Lowercase, kebab-case, ascii-ish canonical tag. Empty result = invalid.

    "  Wide Moat " -> "wide-moat"; "AI/ML" -> "ai-ml"; "růst" -> "rst" (ascii
    fold is out of scope for v1 — disallowed chars are dropped).
    """
    tag = raw.strip().lower()
    tag = _SEPARATORS.sub("-", tag)
    tag = _DISALLOWED.sub("", tag)
    tag = _HYPHEN_RUNS.sub("-", tag).strip("-")
    return tag


def canonicalize_tags(raw_tags: list[str]) -> list[str]:
    """Canonicalize, drop empties, dedupe preserving first-seen order."""
    seen: dict[str, None] = {}
    for raw in raw_tags:
        tag = canonicalize_tag(raw)
        if tag:
            seen.setdefault(tag, None)
    return list(seen)


class ResearchService:
    def __init__(self, notes: NoteRepo, tags: TagRepo) -> None:
        self._notes = notes
        self._tags = tags

    # -- notes ---------------------------------------------------------------
    def create_note(
        self,
        *,
        ticker: str | None = None,
        reference_id: int | None = None,
        analysis_id: int | None = None,
        title: str,
        body: str,
        tags: list[str],
        links: list[NoteLink] | None = None,
    ) -> Note:
        """Create a note about a company (`ticker`), a reference
        (`reference_id`), or an analysis (`analysis_id`) — exactly one must
        be given."""
        self._validate_subject(ticker, reference_id, analysis_id)
        self._validate_title(title)
        note = Note(
            title=title.strip(),
            body=body,
            ticker=ticker.upper().strip() if ticker else None,
            reference_id=reference_id,
            analysis_id=analysis_id,
            tags=canonicalize_tags(tags),
            links=list(links or []),
        )
        stored = self._notes.save(note)
        log.info(
            "note.created",
            note_id=stored.id,
            ticker=stored.ticker,
            reference_id=stored.reference_id,
            analysis_id=stored.analysis_id,
            tags=stored.tags,
        )
        return stored

    def update_note(
        self,
        note_id: int,
        *,
        title: str,
        body: str,
        tags: list[str],
        links: list[NoteLink] | None = None,
    ) -> Note:
        """Edit an existing note's content. The subject (ticker/reference_id/
        analysis_id) is set at creation and never changes."""
        existing = self._notes.get(note_id)
        if existing is None:
            raise NotFoundError(f"note {note_id} not found")
        self._validate_title(title)
        existing.title = title.strip()
        existing.body = body
        existing.tags = canonicalize_tags(tags)
        existing.links = list(links or [])
        stored = self._notes.save(existing)
        log.info("note.updated", note_id=note_id, tags=stored.tags)
        return stored

    def get_note(self, note_id: int) -> Note:
        note = self._notes.get(note_id)
        if note is None:
            raise NotFoundError(f"note {note_id} not found")
        return note

    def list_notes(self, ticker: str) -> list[Note]:
        return self._notes.list_for(ticker.upper().strip())

    def list_notes_for_reference(self, reference_id: int) -> list[Note]:
        return self._notes.list_for_reference(reference_id)

    def list_notes_for_analysis(self, analysis_id: int) -> list[Note]:
        return self._notes.list_for_analysis(analysis_id)

    def delete_note(self, note_id: int) -> None:
        if not self._notes.delete(note_id):
            raise NotFoundError(f"note {note_id} not found")
        log.info("note.deleted", note_id=note_id)

    # -- tags ----------------------------------------------------------------
    def list_tags(self) -> list[str]:
        """The full (canonical) tag vocabulary, for client-side autocomplete."""
        return self._tags.all_tags()

    def merge_tags(self, source: str, target: str) -> int:
        """Fold every use of `source` into `target`; returns notes affected.

        Both names are canonicalized first, so merging "Wide Moat" into
        "moat" behaves identically to merging "wide-moat".
        """
        src = canonicalize_tag(source)
        dst = canonicalize_tag(target)
        if not src or not dst:
            raise ValidationError("tag names must be non-empty after canonicalization")
        if src == dst:
            raise ValidationError("source and target canonicalize to the same tag")
        affected = self._tags.merge(src, dst)
        log.info("tags.merged", source=src, target=dst, notes_affected=affected)
        return affected

    @staticmethod
    def _validate_subject(
        ticker: str | None, reference_id: int | None, analysis_id: int | None
    ) -> None:
        subjects_set = sum(
            (bool(ticker and ticker.strip()), reference_id is not None, analysis_id is not None)
        )
        if subjects_set != 1:
            raise ValidationError(
                "note requires exactly one of ticker, reference_id, or analysis_id"
            )

    @staticmethod
    def _validate_title(title: str) -> None:
        if not title.strip():
            raise ValidationError("note requires a title")
