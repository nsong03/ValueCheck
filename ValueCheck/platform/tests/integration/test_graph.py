"""Graph service: filtered nodes+edges over companies, references, analyses,
notes, and tags (Phase 9b added reference nodes; Phase 9c added analysis
nodes + the tag/link edge-kind distinction)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from equity.adapters.persistence.sqlite import (
    SQLiteAnalysisRepo,
    SQLiteCompanyRepo,
    SQLiteNoteRepo,
    SQLiteReferenceRepo,
)
from equity.application.graph_service import GraphService
from equity.domain.analysis import Analysis
from equity.domain.models import CompanyFinancials
from equity.domain.references import Reference
from equity.domain.research import Note

pytestmark = pytest.mark.integration


@pytest.fixture
def graph_service(
    company_repo: SQLiteCompanyRepo,
    note_repo: SQLiteNoteRepo,
    reference_repo: SQLiteReferenceRepo,
    analysis_repo: SQLiteAnalysisRepo,
) -> GraphService:
    return GraphService(company_repo, note_repo, reference_repo, analysis_repo)


@pytest.fixture
def seeded(
    company_repo: SQLiteCompanyRepo,
    note_repo: SQLiteNoteRepo,
    demo_factory: Callable[..., CompanyFinancials],
) -> None:
    for ticker, sector in (("AAPL", "Technology"), ("TSM", "Technology"), ("XOM", "Energy")):
        fin = demo_factory()
        fin.ticker = ticker
        fin.sector = sector
        company_repo.save(fin)
    note_repo.save(Note(ticker="AAPL", title="a1", body="", tags=["hardware", "moat"]))
    note_repo.save(Note(ticker="AAPL", title="a2", body="", tags=["moat"]))
    note_repo.save(Note(ticker="TSM", title="t1", body="", tags=["hardware"]))
    # XOM: no notes -> isolated company node


class TestFullGraph:
    def test_nodes_and_edges(self, graph_service: GraphService, seeded: None) -> None:
        g = graph_service.build()
        by_kind = {n.id: n for n in g.nodes}

        assert {n.id for n in g.nodes if n.kind == "company"} == {"AAPL", "TSM", "XOM"}
        assert {n.id for n in g.nodes if n.kind == "tag"} == {"tag:hardware", "tag:moat"}
        assert by_kind["AAPL"].sector == "Technology"
        assert by_kind["tag:moat"].label == "moat"

        edges = {(e.source, e.target): e.weight for e in g.edges}
        assert edges == {
            ("AAPL", "tag:hardware"): 1,
            ("AAPL", "tag:moat"): 2,  # two notes carry it
            ("TSM", "tag:hardware"): 1,
        }
        assert all(e.kind == "tag" for e in g.edges)  # incidental (shared-tag) connections

    def test_company_without_notes_is_isolated_node(
        self, graph_service: GraphService, seeded: None
    ) -> None:
        g = graph_service.build()
        assert "XOM" in {n.id for n in g.nodes}
        assert all("XOM" not in (e.source, e.target) for e in g.edges)

    def test_empty_db(self, graph_service: GraphService) -> None:
        g = graph_service.build()
        assert g.nodes == [] and g.edges == []


class TestFilters:
    def test_sector_filter_case_insensitive(
        self, graph_service: GraphService, seeded: None
    ) -> None:
        g = graph_service.build(sector="technology")
        companies = {n.id for n in g.nodes if n.kind == "company"}
        assert companies == {"AAPL", "TSM"}
        assert "XOM" not in {n.id for n in g.nodes}

    def test_sector_filter_scopes_tags_too(self, graph_service: GraphService, seeded: None) -> None:
        g = graph_service.build(sector="Energy")
        assert {n.id for n in g.nodes} == {"XOM"}  # no tag nodes dragged in
        assert g.edges == []

    def test_tickers_filter_impacted_set(self, graph_service: GraphService, seeded: None) -> None:
        g = graph_service.build(tickers=["tsm", " aapl "])  # normalized
        companies = {n.id for n in g.nodes if n.kind == "company"}
        assert companies == {"AAPL", "TSM"}

        g2 = graph_service.build(tickers=["TSM"])
        assert {n.id for n in g2.nodes} == {"TSM", "tag:hardware"}
        assert [(e.source, e.target, e.weight) for e in g2.edges] == [("TSM", "tag:hardware", 1)]


class TestReferenceNodes:
    """Phase 9b: a book/PDF/article is a third node kind, linked into the
    same tag nodes companies use — that shared tag is the "connection"."""

    @pytest.fixture
    def with_references(
        self, reference_repo: SQLiteReferenceRepo, note_repo: SQLiteNoteRepo
    ) -> dict[str, int]:
        book = reference_repo.save(
            Reference(
                kind="book",
                title="The Intelligent Investor",
                location="https://example.com/tii",
                collection="Value Investing",
            )
        )
        paper = reference_repo.save(
            Reference(kind="pdf", title="Quantum Paper", location="C:/refs/quantum.pdf")
        )
        assert book.id is not None and paper.id is not None
        note_repo.save(Note(reference_id=book.id, title="n1", body="", tags=["moat", "value"]))
        # paper carries no notes -> still an isolated node
        return {"book": book.id, "paper": paper.id}

    def test_reference_appears_as_a_node_and_links_via_shared_tag(
        self, graph_service: GraphService, seeded: None, with_references: dict[str, int]
    ) -> None:
        g = graph_service.build()
        book_id = f"reference:{with_references['book']}"
        paper_id = f"reference:{with_references['paper']}"

        refs = {n.id: n for n in g.nodes if n.kind == "reference"}
        assert set(refs) == {book_id, paper_id}
        assert refs[book_id].label == "The Intelligent Investor"
        assert refs[book_id].collection == "Value Investing"

        # AAPL and the book both carry "moat" -> connected through the tag node
        edges = {(e.source, e.target) for e in g.edges}
        assert (book_id, "tag:moat") in edges
        assert ("AAPL", "tag:moat") in edges

    def test_reference_without_notes_is_isolated(
        self, graph_service: GraphService, with_references: dict[str, int]
    ) -> None:
        g = graph_service.build()
        paper_id = f"reference:{with_references['paper']}"
        assert paper_id in {n.id for n in g.nodes}
        assert all(paper_id not in (e.source, e.target) for e in g.edges)

    def test_collection_filter_scopes_references(
        self, graph_service: GraphService, with_references: dict[str, int]
    ) -> None:
        g = graph_service.build(collection="Value Investing")
        assert {n.id for n in g.nodes if n.kind == "reference"} == {
            f"reference:{with_references['book']}"
        }

    def test_tickers_filter_drops_references(
        self, graph_service: GraphService, seeded: None, with_references: dict[str, int]
    ) -> None:
        """An impacted-ticker search view is company-scoped; references (not
        covered by search yet) don't clutter that focused view."""
        g = graph_service.build(tickers=["AAPL"])
        assert {n.id for n in g.nodes if n.kind == "reference"} == set()


class TestAnalysisNodes:
    """Phase 9c: an analysis is a fourth node kind with TWO ways to connect
    to the rest of the graph — incidental (shared tag, like company/
    reference) and deliberate (an explicit "link" edge to its constituents)."""

    def test_analysis_appears_and_links_via_shared_tag(
        self,
        graph_service: GraphService,
        seeded: None,
        note_repo: SQLiteNoteRepo,
        analysis_repo: SQLiteAnalysisRepo,
    ) -> None:
        model = analysis_repo.save(Analysis(kind="portfolio", title="Core Holdings"))
        assert model.id is not None
        note_repo.save(Note(analysis_id=model.id, title="n", body="", tags=["moat"]))

        g = graph_service.build()
        an_id = f"analysis:{model.id}"
        analyses = {n.id: n for n in g.nodes if n.kind == "analysis"}
        assert analyses[an_id].label == "Core Holdings"

        tag_edges = {(e.source, e.target) for e in g.edges if e.kind == "tag"}
        assert (an_id, "tag:moat") in tag_edges
        assert ("AAPL", "tag:moat") in tag_edges  # both connect through the tag

    def test_explicit_company_link_is_a_link_edge_not_a_tag_edge(
        self,
        graph_service: GraphService,
        seeded: None,
        analysis_repo: SQLiteAnalysisRepo,
    ) -> None:
        model = analysis_repo.save(Analysis(kind="correlation-study", title="Semis"))
        assert model.id is not None
        analysis_repo.add_company(model.id, "AAPL")  # no note, no shared tag involved

        g = graph_service.build()
        an_id = f"analysis:{model.id}"
        link_edges = {(e.source, e.target, e.weight) for e in g.edges if e.kind == "link"}
        assert (an_id, "AAPL", 1) in link_edges or ("AAPL", an_id, 1) in link_edges

    def test_explicit_reference_link(
        self,
        graph_service: GraphService,
        reference_repo: SQLiteReferenceRepo,
        analysis_repo: SQLiteAnalysisRepo,
    ) -> None:
        ref = reference_repo.save(
            Reference(kind="pdf", title="Paper", location="https://example.com/paper")
        )
        model = analysis_repo.save(Analysis(kind="dcf-variant", title="Model"))
        assert ref.id is not None and model.id is not None
        analysis_repo.add_reference(model.id, ref.id)

        g = graph_service.build()
        an_id = f"analysis:{model.id}"
        ref_id = f"reference:{ref.id}"
        link_edges = {(e.source, e.target) for e in g.edges if e.kind == "link"}
        assert (an_id, ref_id) in link_edges or (ref_id, an_id) in link_edges

    def test_analysis_to_analysis_link(
        self, graph_service: GraphService, analysis_repo: SQLiteAnalysisRepo
    ) -> None:
        a = analysis_repo.save(Analysis(kind="correlation-study", title="A"))
        b = analysis_repo.save(Analysis(kind="portfolio", title="B"))
        assert a.id is not None and b.id is not None
        analysis_repo.add_link(a.id, b.id)

        g = graph_service.build()
        a_id, b_id = f"analysis:{a.id}", f"analysis:{b.id}"
        link_edges = {(e.source, e.target) for e in g.edges if e.kind == "link"}
        assert (a_id, b_id) in link_edges or (b_id, a_id) in link_edges

    def test_analysis_without_notes_or_links_is_isolated(
        self, graph_service: GraphService, analysis_repo: SQLiteAnalysisRepo
    ) -> None:
        model = analysis_repo.save(Analysis(kind="other", title="Untouched"))
        assert model.id is not None
        g = graph_service.build()
        an_id = f"analysis:{model.id}"
        assert an_id in {n.id for n in g.nodes}
        assert all(an_id not in (e.source, e.target) for e in g.edges)

    def test_tickers_filter_drops_analyses(
        self, graph_service: GraphService, seeded: None, analysis_repo: SQLiteAnalysisRepo
    ) -> None:
        analysis_repo.save(Analysis(kind="other", title="Unrelated"))
        g = graph_service.build(tickers=["AAPL"])
        assert {n.id for n in g.nodes if n.kind == "analysis"} == set()
