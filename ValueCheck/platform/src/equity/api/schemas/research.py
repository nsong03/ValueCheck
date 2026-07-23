"""Note + tag DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from equity.domain.research import Note, NoteLink


class NoteLinkIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2000)


class NoteLinkOut(BaseModel):
    label: str
    url: str

    @classmethod
    def from_domain(cls, link: NoteLink) -> NoteLinkOut:
        return cls(label=link.label, url=link.url)


class NoteIn(BaseModel):
    """Exactly one of `ticker`/`reference_id`/`analysis_id` must be set — a
    note is about a company, a reference (a book, PDF, or article), or an
    analysis (a model/study), never more than one or none."""

    ticker: str | None = Field(default=None, min_length=1, max_length=12)
    reference_id: int | None = None
    analysis_id: int | None = None
    title: str = Field(min_length=1, max_length=300)
    body: str = ""
    tags: list[str] = Field(default_factory=list, max_length=50)
    links: list[NoteLinkIn] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _exactly_one_subject(self) -> NoteIn:
        subjects_set = sum(
            (self.ticker is not None, self.reference_id is not None, self.analysis_id is not None)
        )
        if subjects_set != 1:
            raise ValueError("exactly one of ticker, reference_id, or analysis_id is required")
        return self


class NoteUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = ""
    tags: list[str] = Field(default_factory=list, max_length=50)
    links: list[NoteLinkIn] = Field(default_factory=list, max_length=20)


class NoteOut(BaseModel):
    id: int
    ticker: str | None
    reference_id: int | None
    analysis_id: int | None
    title: str
    body: str
    tags: list[str]  # canonical form (server-side invariant)
    links: list[NoteLinkOut]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, note: Note) -> NoteOut:
        assert note.id is not None and note.created_at and note.updated_at
        return cls(
            id=note.id,
            ticker=note.ticker,
            reference_id=note.reference_id,
            analysis_id=note.analysis_id,
            title=note.title,
            body=note.body,
            tags=note.tags,
            links=[NoteLinkOut.from_domain(link) for link in note.links],
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
