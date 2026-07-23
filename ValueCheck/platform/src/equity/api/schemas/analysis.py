"""Analysis DTOs: the balcony — models/studies with explicit links to
companies, references, and other analyses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from equity.domain.analysis import Analysis


class AnalysisIn(BaseModel):
    kind: str = Field(
        min_length=1, max_length=50, examples=["dcf-variant", "portfolio", "correlation-study"]
    )
    title: str = Field(min_length=1, max_length=300)
    summary: str = ""


class AnalysisUpdate(BaseModel):
    """Every field optional — only supplied fields change."""

    kind: str | None = Field(default=None, min_length=1, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    summary: str | None = None


class AnalysisOut(BaseModel):
    id: int
    kind: str
    title: str
    summary: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, a: Analysis) -> AnalysisOut:
        assert a.id is not None and a.created_at is not None and a.updated_at is not None
        return cls(
            id=a.id,
            kind=a.kind,
            title=a.title,
            summary=a.summary,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )


class AnalysisCompaniesOut(BaseModel):
    tickers: list[str]


class AnalysisReferencesOut(BaseModel):
    reference_ids: list[int]


class AnalysisLinksOut(BaseModel):
    analysis_ids: list[int]


class TickerIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)


class ReferenceIdIn(BaseModel):
    reference_id: int


class LinkedAnalysisIn(BaseModel):
    linked_analysis_id: int
