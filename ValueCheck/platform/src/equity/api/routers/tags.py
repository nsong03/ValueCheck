"""Tags router: vocabulary for autocomplete + merge."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from equity.api.deps import get_research
from equity.api.schemas.research import TagMergeIn, TagMergeOut, TagsOut
from equity.application.research_service import ResearchService, canonicalize_tag

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=TagsOut)
def list_tags(research: Annotated[ResearchService, Depends(get_research)]) -> TagsOut:
    """Every canonical tag in use (client-side fuzzy suggest feeds on this)."""
    return TagsOut(tags=research.list_tags())


@router.post("/merge", response_model=TagMergeOut)
def merge_tags(
    payload: TagMergeIn,
    research: Annotated[ResearchService, Depends(get_research)],
) -> TagMergeOut:
    affected = research.merge_tags(payload.source, payload.target)
    return TagMergeOut(
        source=canonicalize_tag(payload.source),
        target=canonicalize_tag(payload.target),
        notes_affected=affected,
    )
