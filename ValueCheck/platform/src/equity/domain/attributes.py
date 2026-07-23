"""Attribute entities: typed, namespaced facts about a company (region,
custom sector, quality scores, status), sourced from a note or a direct
edit, with full history. Pure data, no I/O — canonicalization and
validation are application concerns (equity.application.attribute_service),
the same split as equity.domain.research.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ValueType = Literal["text", "number", "scale"]
AttributeSource = Literal["note", "grid"]


@dataclass(frozen=True, slots=True)
class AttributeDefinition:
    """The schema for one attribute key: how to render, validate, and sort it.

    Created implicitly the first time a key is used (`value_type` defaults to
    "text"); curatable later — promote to "scale", attach `allowed_values`/
    `colors` for an enum like `status` — without a migration. This is what
    lets the tag vocabulary stay flexible now and get quantifiable later.
    """

    key: str
    label: str
    value_type: ValueType = "text"
    scale_min: float | None = None
    scale_max: float | None = None
    allowed_values: list[str] | None = None
    colors: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class AttributeValue:
    """One historical entry for one (ticker, key).

    Append-only: the "current" value is the latest entry by `created_at`,
    not a separate row — there is nothing to keep in sync. `id`/`created_at`
    are None until the repository persists it. `note_id` is the note that
    justified this value, if any; it survives that note's deletion as NULL
    (the fact stays even if its provenance is cleaned up later).
    """

    ticker: str
    key: str
    value: str
    source: AttributeSource
    id: int | None = None
    note_id: int | None = None
    reason: str | None = None
    created_at: datetime | None = None
