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


@dataclass(slots=True)
class Note:
    """One research note attached to a company.

    `id` and the timestamps are None until the repository persists the note —
    identity and clock are infrastructure concerns, so the repo assigns them.
    Tags are plain strings here; canonicalization is a Phase 7 service concern.
    """

    ticker: str
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
