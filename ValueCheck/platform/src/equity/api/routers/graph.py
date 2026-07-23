"""Graph router: filtered research subgraph (companies + tags)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from equity.api.deps import get_graph
from equity.api.schemas.explore import GraphOut
from equity.application.graph_service import GraphService

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphOut)
def graph(
    service: Annotated[GraphService, Depends(get_graph)],
    sector: Annotated[str | None, Query(description="Exact sector filter (companies)")] = None,
    tickers: Annotated[
        list[str] | None,
        Query(description="Restrict to these tickers (e.g. a search's impacted set)"),
    ] = None,
    collection: Annotated[
        str | None, Query(description="Exact collection filter (references)")
    ] = None,
) -> GraphOut:
    """Nodes+edges for the research graph, optionally filtered."""
    return GraphOut.from_domain(
        service.build(sector=sector, tickers=tickers, collection=collection)
    )
