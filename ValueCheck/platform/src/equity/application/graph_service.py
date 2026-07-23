"""Graph use-case: the research web as filtered nodes + edges.

v1 model (visualization polish is deferred per product decision):
- nodes: companies (id = ticker), references (id = "reference:<id>" — books,
  PDFs, articles, webpages, Phase 9b), analyses (id = "analysis:<id>" — the
  balcony, Phase 9c: models/studies), and tags (id = "tag:<name>")
- edges carry a `kind`, since two subjects can be connected for two very
  different reasons:
    - "tag": incidental — both have notes carrying the same tag. Weight =
      how many notes carry it.
    - "link": deliberate — an analysis explicitly includes this company/
      reference/other analysis as a constituent (BUILD_SPEC Phase 9c).
      Weight is always 1; the fact of the link is binary.
  A company note and a reference note sharing a tag land on the same tag
  node — that's how they "connect" without any direct edge between them.
  An analysis's constituents get a direct edge instead, because that
  relationship is a fact about the analysis, not a coincidence of tagging.
- filters: `sector` scopes companies; `collection` scopes references
  (case-insensitive exact match, each independent of the other); `tickers`
  (e.g. the impacted set from a search, company-scoped only for now)
  restricts to those tickers AND drops references/analyses from that
  particular view, since search doesn't cover them yet. All filters empty
  means the whole graph.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from equity.logging import get_logger
from equity.ports.repository import AnalysisRepo, CompanyRepo, NoteRepo, ReferenceRepo

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: str  # ticker, "reference:<id>", "analysis:<id>", or "tag:<name>"
    label: str
    kind: str  # "company" | "reference" | "analysis" | "tag"
    sector: str | None = None  # companies only
    collection: str | None = None  # references only


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    target: str
    weight: int
    kind: str = "tag"  # "tag" (incidental, weighted) | "link" (explicit, weight 1)


@dataclass(frozen=True, slots=True)
class GraphData:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


class GraphService:
    def __init__(
        self,
        companies: CompanyRepo,
        notes: NoteRepo,
        references: ReferenceRepo,
        analyses: AnalysisRepo,
    ) -> None:
        self._companies = companies
        self._notes = notes
        self._references = references
        self._analyses = analyses

    def build(
        self,
        sector: str | None = None,
        tickers: list[str] | None = None,
        collection: str | None = None,
    ) -> GraphData:
        wanted = {t.upper().strip() for t in tickers} if tickers else None

        nodes: list[GraphNode] = []
        tag_edge_weights: Counter[tuple[str, str]] = Counter()
        link_edges: set[tuple[str, str]] = set()
        tag_nodes: dict[str, GraphNode] = {}

        def link_tags(subject_id: str, tags: list[str]) -> None:
            for tag in tags:
                tag_id = f"tag:{tag}"
                if tag_id not in tag_nodes:
                    tag_nodes[tag_id] = GraphNode(id=tag_id, label=tag, kind="tag")
                tag_edge_weights[(subject_id, tag_id)] += 1

        def link_explicit(a: str, b: str) -> None:
            link_edges.add((a, b) if a <= b else (b, a))

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
                link_tags(ticker, note.tags)

        # An impacted-ticker search view is company-scoped only; references
        # and analyses (not covered by search yet) don't clutter that view.
        if wanted is None:
            for ref in self._references.list_all():
                if collection is not None and ref.collection.lower() != collection.lower():
                    continue
                ref_id = f"reference:{ref.id}"
                nodes.append(
                    GraphNode(
                        id=ref_id, label=ref.title, kind="reference", collection=ref.collection
                    )
                )
                assert ref.id is not None
                for note in self._notes.list_for_reference(ref.id):
                    link_tags(ref_id, note.tags)

            for analysis in self._analyses.list_all():
                assert analysis.id is not None
                an_id = f"analysis:{analysis.id}"
                nodes.append(GraphNode(id=an_id, label=analysis.title, kind="analysis"))
                for note in self._notes.list_for_analysis(analysis.id):
                    link_tags(an_id, note.tags)
                for company_ticker in self._analyses.list_companies(analysis.id):
                    link_explicit(an_id, company_ticker)
                for reference_id in self._analyses.list_references(analysis.id):
                    link_explicit(an_id, f"reference:{reference_id}")
                for linked_id in self._analyses.list_links(analysis.id):
                    link_explicit(an_id, f"analysis:{linked_id}")

        nodes.extend(tag_nodes.values())
        node_ids = {n.id for n in nodes}
        edges = [
            GraphEdge(source=src, target=dst, weight=w, kind="tag")
            for (src, dst), w in sorted(tag_edge_weights.items())
        ]
        edges.extend(
            GraphEdge(source=src, target=dst, weight=1, kind="link")
            for src, dst in sorted(link_edges)
            # a link's other end may have been filtered out (e.g. sector) — don't
            # emit a dangling edge to a node that isn't actually in this view
            if src in node_ids and dst in node_ids
        )
        log.info(
            "graph.built",
            sector=sector,
            tickers=sorted(wanted) if wanted else None,
            collection=collection,
            nodes=len(nodes),
            edges=len(edges),
        )
        return GraphData(nodes=nodes, edges=edges)
