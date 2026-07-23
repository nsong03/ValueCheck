"""The knowledge library: books, articles, PDFs, and webpages that research
notes can attach to (Phase 9b). Pure data, no I/O.

`kind` is deliberately free text rather than a rigid enum — same "flexible
now, curate later" philosophy as `equity.domain.attributes` — so a new kind
of source never needs a migration. `collection` is a folder-derived path
(e.g. "TechnicalReading/Valuation"), letting a scanned library stay organized
by however it's actually organized on disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ReferenceOrigin = Literal["manual", "scan"]


@dataclass(slots=True)
class Reference:
    """One tracked source: `location` is either an http(s) URL or an
    absolute local filesystem path. `id`/`added_at` are None until the
    repository persists it."""

    kind: str  # suggested vocabulary: "pdf" | "webpage" | "book" | "article" | "other"
    title: str
    location: str
    collection: str = ""
    origin: ReferenceOrigin = "manual"
    id: int | None = None
    added_at: datetime | None = None
