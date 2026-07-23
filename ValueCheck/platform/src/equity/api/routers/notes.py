"""Notes router: research notes CRUD (tags canonicalized server-side)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from equity.api.deps import get_research
from equity.api.schemas.research import NoteIn, NoteOut, NoteUpdate
from equity.application.research_service import ResearchService
from equity.domain.research import NoteLink

router = APIRouter(tags=["notes"])


@router.post("/notes", response_model=NoteOut, status_code=201)
def create_note(
    payload: NoteIn,
    research: Annotated[ResearchService, Depends(get_research)],
) -> NoteOut:
    note = research.create_note(
        ticker=payload.ticker,
        reference_id=payload.reference_id,
        analysis_id=payload.analysis_id,
        title=payload.title,
        body=payload.body,
        tags=payload.tags,
        links=[NoteLink(label=link.label, url=link.url) for link in payload.links],
    )
    return NoteOut.from_domain(note)


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(
    note_id: int,
    research: Annotated[ResearchService, Depends(get_research)],
) -> NoteOut:
    return NoteOut.from_domain(research.get_note(note_id))


@router.put("/notes/{note_id}", response_model=NoteOut)
def update_note(
    note_id: int,
    payload: NoteUpdate,
    research: Annotated[ResearchService, Depends(get_research)],
) -> NoteOut:
    note = research.update_note(
        note_id,
        title=payload.title,
        body=payload.body,
        tags=payload.tags,
        links=[NoteLink(label=link.label, url=link.url) for link in payload.links],
    )
    return NoteOut.from_domain(note)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(
    note_id: int,
    research: Annotated[ResearchService, Depends(get_research)],
) -> Response:
    research.delete_note(note_id)
    return Response(status_code=204)


@router.get("/companies/{ticker}/notes", response_model=list[NoteOut])
def list_notes(
    ticker: str,
    research: Annotated[ResearchService, Depends(get_research)],
) -> list[NoteOut]:
    """Notes for one company, newest first."""
    return [NoteOut.from_domain(n) for n in research.list_notes(ticker)]


@router.get("/references/{reference_id}/notes", response_model=list[NoteOut])
def list_notes_for_reference(
    reference_id: int,
    research: Annotated[ResearchService, Depends(get_research)],
) -> list[NoteOut]:
    """Notes for one reference (book/PDF/article/webpage), newest first."""
    return [NoteOut.from_domain(n) for n in research.list_notes_for_reference(reference_id)]


@router.get("/analyses/{analysis_id}/notes", response_model=list[NoteOut])
def list_notes_for_analysis(
    analysis_id: int,
    research: Annotated[ResearchService, Depends(get_research)],
) -> list[NoteOut]:
    """Notes for one analysis (a model/study, the balcony), newest first."""
    return [NoteOut.from_domain(n) for n in research.list_notes_for_analysis(analysis_id)]
