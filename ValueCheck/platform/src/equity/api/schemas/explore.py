"""Search + graph DTOs."""

from __future__ import annotations

from pydantic import BaseModel

from equity.application.graph_service import GraphData
from equity.application.search_service import SearchResult
from equity.domain.research import SearchHit


class SearchHitOut(BaseModel):
    note_id: int
    ticker: str
    title: str
    snippet: str

    @classmethod
    def from_domain(cls, hit: SearchHit) -> SearchHitOut:
        return cls(
            note_id=hit.note_id,
            ticker=hit.ticker,
            title=hit.title,
            snippet=hit.snippet,
        )


class SearchResultOut(BaseModel):
    query: str
    hits: list[SearchHitOut]
    impacted_tickers: list[str]  # best-match-first, unique

    @classmethod
    def from_domain(cls, result: SearchResult) -> SearchResultOut:
        return cls(
            query=result.query,
            hits=[SearchHitOut.from_domain(h) for h in result.hits],
            impacted_tickers=result.impacted_tickers,
        )


class GraphNodeOut(BaseModel):
    id: str
    label: str
    kind: str  # "company" | "reference" | "analysis" | "tag"
    sector: str | None = None  # companies only
    collection: str | None = None  # references only


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    weight: int
    kind: str  # "tag" (incidental, weighted) | "link" (explicit constituent, weight 1)


class GraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]

    @classmethod
    def from_domain(cls, graph: GraphData) -> GraphOut:
        return cls(
            nodes=[
                GraphNodeOut(
                    id=n.id, label=n.label, kind=n.kind, sector=n.sector, collection=n.collection
                )
                for n in graph.nodes
            ],
            edges=[
                GraphEdgeOut(source=e.source, target=e.target, weight=e.weight, kind=e.kind)
                for e in graph.edges
            ],
        )
