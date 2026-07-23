"""Research entities: notes and their tags. Pure data, no I/O.

Minimal shapes introduced in Phase 3 so the repository ports have something
to store; the research workflows around them (tag canonicalization, merge,
fuzzy suggest) arrive in Phase 7 per BUILD_SPEC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One note matched by a full-text query, best matches first.

    `snippet` is a short excerpt with the match highlighted; `score` is the
    index's relevance rank (lower = better in FTS5's bm25 convention —
    consumers should treat it as opaque ordering, not a probability).
    """

    note_id: int
    ticker: str
    title: str
    snippet: str
    score: float


@dataclass(frozen=True, slots=True)
class NoteLink:
    """One inline link a note cites — a web URL or a path on this machine.

    Freeform: the domain doesn't validate reachability, only that the caller
    supplied a label + location. `url` holds either an http(s) URL or a local
    filesystem path (Phase 9b: the knowledge library).
    """

    label: str
    url: str


@dataclass(slots=True)
class Note:
    """One research note, attached to a company, a reference (a book, PDF,
    or article), or an analysis (a model/study, Phase 9c) — exactly one of
    `ticker`/`reference_id`/`analysis_id` is set.

    `id` and the timestamps are None until the repository persists the note —
    identity and clock are infrastructure concerns, so the repo assigns them.
    Tags are plain strings here; canonicalization is a service concern
    (equity.application.research_service), same for all three kinds of
    subject — that shared vocabulary is what lets a company note, a book
    note, and a model note end up connected in the research graph.
    """

    title: str
    body: str
    ticker: str | None = None
    reference_id: int | None = None
    analysis_id: int | None = None
    tags: list[str] = field(default_factory=list)
    links: list[NoteLink] = field(default_factory=list)
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
