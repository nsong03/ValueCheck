"""FTS5 search: trigger-synced index, sanitized queries, impacted tickers."""

from __future__ import annotations

import pytest

from equity.adapters.persistence.sqlite import SQLiteDatabase, SQLiteNoteRepo
from equity.adapters.search.fts5 import FTS5SearchIndex, build_match_query
from equity.application.search_service import SearchService
from equity.domain.research import Note

pytestmark = pytest.mark.integration


@pytest.fixture
def index(db: SQLiteDatabase) -> FTS5SearchIndex:
    return FTS5SearchIndex(db)


@pytest.fixture
def service(index: FTS5SearchIndex) -> SearchService:
    return SearchService(index)


def note(ticker: str, title: str, body: str) -> Note:
    return Note(ticker=ticker, title=title, body=body)


class TestMatchQuerySanitization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("chip shortage", '"chip" OR "shortage"*'),
            ("TSMC", '"TSMC"*'),
            ('"quoted" AND (operators)', '"quoted" OR "AND" OR "operators"*'),
            ("!!!", ""),
            ("", ""),
        ],
    )
    def test_build_match_query(self, raw: str, expected: str) -> None:
        assert build_match_query(raw) == expected


class TestSearch:
    def test_finds_by_body_word(self, note_repo: SQLiteNoteRepo, index: FTS5SearchIndex) -> None:
        note_repo.save(note("AAPL", "Ecosystem thesis", "Sticky services revenue."))
        note_repo.save(note("TSM", "Fab risk", "Chip shortage exposure at fabs."))

        hits = index.search_notes("chip shortage")
        assert [h.ticker for h in hits] == ["TSM"]
        assert hits[0].title == "Fab risk"
        assert "[shortage]" in hits[0].snippet or "[Chip]" in hits[0].snippet

    def test_finds_by_title_word(self, note_repo: SQLiteNoteRepo, index: FTS5SearchIndex) -> None:
        note_repo.save(note("AAPL", "Ecosystem thesis", "body text"))
        assert [h.ticker for h in index.search_notes("ecosystem")] == ["AAPL"]

    def test_prefix_match_on_last_token(
        self, note_repo: SQLiteNoteRepo, index: FTS5SearchIndex
    ) -> None:
        note_repo.save(note("TSM", "Fab risk", "Chip shortage exposure."))
        assert [h.ticker for h in index.search_notes("shor")] == ["TSM"]

    def test_update_reindexes(self, note_repo: SQLiteNoteRepo, index: FTS5SearchIndex) -> None:
        stored = note_repo.save(note("AAPL", "t", "original wording"))
        stored.body = "completely different topic"
        note_repo.save(stored)

        assert index.search_notes("wording") == []
        assert [h.note_id for h in index.search_notes("topic")] == [stored.id]

    def test_delete_removes_from_index(
        self, note_repo: SQLiteNoteRepo, index: FTS5SearchIndex
    ) -> None:
        stored = note_repo.save(note("AAPL", "t", "ephemeral content"))
        assert stored.id is not None
        assert len(index.search_notes("ephemeral")) == 1
        note_repo.delete(stored.id)
        assert index.search_notes("ephemeral") == []

    def test_garbage_queries_return_empty_not_error(self, index: FTS5SearchIndex) -> None:
        assert index.search_notes('"unbalanced AND ((') == []
        assert index.search_notes("!!!") == []
        assert index.search_notes("nomatchanywhere") == []

    def test_limit(self, note_repo: SQLiteNoteRepo, index: FTS5SearchIndex) -> None:
        for i in range(5):
            note_repo.save(note("AAPL", f"note {i}", "recurring theme"))
        assert len(index.search_notes("theme", limit=3)) == 3


class TestImpactedTickers:
    def test_dedupes_best_first(self, note_repo: SQLiteNoteRepo, service: SearchService) -> None:
        # TSM mentions the term twice across notes; NVDA once
        note_repo.save(note("TSM", "Fab", "chip shortage chip shortage risk"))
        note_repo.save(note("NVDA", "Supply", "chip shortage upside"))
        note_repo.save(note("TSM", "More", "chip inventory"))

        result = service.impacted("chip shortage")
        assert set(result.impacted_tickers) == {"TSM", "NVDA"}
        assert len(result.impacted_tickers) == 2  # deduped
        assert result.hits[0].ticker == "TSM"  # densest match ranks first

    def test_no_hits(self, service: SearchService) -> None:
        result = service.impacted("nothing indexed")
        assert result.hits == []
        assert result.impacted_tickers == []
