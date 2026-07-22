"""Search router: event query -> matching notes + impacted tickers."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from equity.api.deps import get_search
from equity.api.schemas.explore import SearchResultOut
from equity.application.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResultOut)
def search(
    service: Annotated[SearchService, Depends(get_search)],
    q: Annotated[str, Query(min_length=1, max_length=200, description="Event/free text")],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SearchResultOut:
    """Full-text search over note titles/bodies; returns impacted tickers."""
    return SearchResultOut.from_domain(service.impacted(q, limit=limit))
