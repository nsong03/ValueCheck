"""Graph use-case: the research web as filtered nodes + edges.

v1 model (visualization polish is deferred per product decision):
- nodes: companies (id = ticker) and tags (id = "tag:<name>")
- edges: company <-> tag, weight = number of that company's notes carrying
  the tag; companies with zero notes still appear as isolated nodes
- filters: `sector` (exact, case-insensitive) or `tickers` (e.g. the
  impacted set from a search) — both empty means the whole graph
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from equity.logging import get_logger
from equity.ports.repository import CompanyRepo, NoteRepo

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: str  # ticker, or "tag:<name>"
    label: str
    kind: str  # "company" | "tag"
    sector: str | None = None  # companies only


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    target: str
    weight: int


@dataclass(frozen=True, slots=True)
class GraphData:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


class GraphService:
    def __init__(self, companies: CompanyRepo, notes: NoteRepo) -> None:
        self._companies = companies
        self._notes = notes

    def build(
        self,
        sector: str | None = None,
        tickers: list[str] | None = None,
    ) -> GraphData:
        wanted = {t.upper().strip() for t in tickers} if tickers else None

        nodes: list[GraphNode] = []
        edge_weights: Counter[tuple[str, str]] = Counter()
        tag_nodes: dict[str, GraphNode] = {}

        for ticker in self._companies.list_tickers():
            if wanted is not None and ticker not in wanted:
                continue
            fin = self._companies.get(ticker)
            if fin is None:  # deleted between list and get; skip
                continue
            if sector is not None and fin.sector.lower() != sector.lower():
                continue
            nodes.append(GraphNode(id=ticker, label=fin.name, kind="company", sector=fin.sector))
            for note in self._notes.list_for(ticker):
                for tag in note.tags:
                    tag_id = f"tag:{tag}"
                    if tag_id not in tag_nodes:
                        tag_nodes[tag_id] = GraphNode(id=tag_id, label=tag, kind="tag")
                    edge_weights[(ticker, tag_id)] += 1

        nodes.extend(tag_nodes.values())
        edges = [
            GraphEdge(source=src, target=dst, weight=w)
            for (src, dst), w in sorted(edge_weights.items())
        ]
        log.info(
            "graph.built",
            sector=sector,
            tickers=sorted(wanted) if wanted else None,
            nodes=len(nodes),
            edges=len(edges),
        )
        return GraphData(nodes=nodes, edges=edges)
