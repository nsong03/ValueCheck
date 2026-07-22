"""Note + tag DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from equity.domain.research import Note


class NoteIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    title: str = Field(min_length=1, max_length=300)
    body: str = ""
    tags: list[str] = Field(default_factory=list, max_length=50)


class NoteUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = ""
    tags: list[str] = Field(default_factory=list, max_length=50)


class NoteOut(BaseModel):
    id: int
    ticker: str
    title: str
    body: str
    tags: list[str]  # canonical form (server-side invariant)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, note: Note) -> NoteOut:
        assert note.id is not None and note.created_at and note.updated_at
        return cls(
            id=note.id,
            ticker=note.ticker,
            title=note.title,
            body=note.body,
            tags=note.tags,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )


class TagsOut(BaseModel):
    tags: list[str]


class TagMergeIn(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=100)


class TagMergeOut(BaseModel):
    source: str  # canonical form that was folded away
    target: str  # canonical form everything now carries
    notes_affected: int
