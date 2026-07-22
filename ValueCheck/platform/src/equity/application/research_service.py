"""Research use-cases: notes CRUD and the tag vocabulary.

Tag canonicalization is a SERVER-side invariant (BUILD_SPEC Phase 7): every
tag is stored in canonical form no matter how the client spelled it, so
"Wide Moat", "wide_moat" and "wide-moat" are one tag. The client's fuzzy
suggest (fuse.js) only helps typing; it never defines identity.
"""

from __future__ import annotations

import re

from equity.domain.research import Note
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
    def create_note(self, ticker: str, title: str, body: str, tags: list[str]) -> Note:
        self._validate(ticker, title)
        note = Note(
            ticker=ticker.upper().strip(),
            title=title.strip(),
            body=body,
            tags=canonicalize_tags(tags),
        )
        stored = self._notes.save(note)
        log.info("note.created", note_id=stored.id, ticker=stored.ticker, tags=stored.tags)
        return stored

    def update_note(self, note_id: int, *, title: str, body: str, tags: list[str]) -> Note:
        existing = self._notes.get(note_id)
        if existing is None:
            raise NotFoundError(f"note {note_id} not found")
        self._validate(existing.ticker, title)
        existing.title = title.strip()
        existing.body = body
        existing.tags = canonicalize_tags(tags)
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
    def _validate(ticker: str, title: str) -> None:
        if not ticker.strip():
            raise ValidationError("note requires a ticker")
        if not title.strip():
            raise ValidationError("note requires a title")
