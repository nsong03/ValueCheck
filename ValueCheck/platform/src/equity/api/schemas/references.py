"""Reference DTOs: the knowledge library (books, articles, PDFs, webpages)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from equity.domain.references import Reference


class ReferenceIn(BaseModel):
    """Manually add a reference (a webpage, book, article, or a local file
    you don't want to wait for a scan to pick up)."""

    kind: str = Field(min_length=1, max_length=30, examples=["webpage", "book", "article", "pdf"])
    title: str = Field(min_length=1, max_length=300)
    location: str = Field(min_length=1, max_length=2000, description="A URL or a local file path.")
    collection: str = Field(default="", max_length=200)


class ReferenceUpdate(BaseModel):
    """Every field optional — only supplied fields change. `location` isn't
    editable here; delete and re-add if a source moved."""

    kind: str | None = Field(default=None, min_length=1, max_length=30)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    collection: str | None = Field(default=None, max_length=200)


class ReferenceOut(BaseModel):
    id: int
    kind: str
    title: str
    location: str
    collection: str
    origin: str
    added_at: datetime

    @classmethod
    def from_domain(cls, ref: Reference) -> ReferenceOut:
        assert ref.id is not None and ref.added_at is not None
        return cls(
            id=ref.id,
            kind=ref.kind,
            title=ref.title,
            location=ref.location,
            collection=ref.collection,
            origin=ref.origin,
            added_at=ref.added_at,
        )


class ReferenceScanOut(BaseModel):
    created: list[ReferenceOut]
