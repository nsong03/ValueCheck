"""Graph service: filtered nodes+edges over companies, notes, and tags."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from equity.adapters.persistence.sqlite import SQLiteCompanyRepo, SQLiteNoteRepo
from equity.application.graph_service import GraphService
from equity.domain.models import CompanyFinancials
from equity.domain.research import Note

pytestmark = pytest.mark.integration


@pytest.fixture
def graph_service(company_repo: SQLiteCompanyRepo, note_repo: SQLiteNoteRepo) -> GraphService:
    return GraphService(company_repo, note_repo)


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
