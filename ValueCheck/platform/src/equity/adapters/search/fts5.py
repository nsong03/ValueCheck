"""SQLite FTS5 search adapter (query-only).

The `notes_fts` index is created and kept in sync by migration 0002's
triggers, so this adapter never writes — it only queries. User input is
sanitized into quoted OR-joined tokens (the last token as a prefix match),
because raw FTS5 MATCH syntax throws on stray quotes/operators and an event
query ("chip shortage TSMC") wants recall over strictness.
"""

from __future__ import annotations

import re

from equity.adapters.persistence.sqlite import SQLiteDatabase
from equity.domain.research import SearchHit
from equity.logging import get_logger

log = get_logger(__name__)

_TOKEN = re.compile(r"[A-Za-z0-9]+")


def build_match_query(raw: str) -> str:
    """User text -> safe FTS5 MATCH expression. Empty when nothing usable."""
    tokens = _TOKEN.findall(raw)
    if not tokens:
        return ""
    quoted = [f'"{t}"' for t in tokens[:-1]]
    quoted.append(f'"{tokens[-1]}"*')  # last token matches as a prefix (typing aid)
    return " OR ".join(quoted)


class FTS5SearchIndex:
    """Implements ports.search.SearchIndex over the notes_fts virtual table."""

    def __init__(self, db: SQLiteDatabase) -> None:
        self._db = db

    def search_notes(self, query: str, limit: int = 50) -> list[SearchHit]:
        match = build_match_query(query)
        if not match:
            return []
        with self._db.connection() as conn:
            rows = conn.execute(
                """SELECT n.id, n.ticker, n.title,
                          snippet(notes_fts, 1, '[', ']', ' … ', 12) AS snip,
                          rank
                   FROM notes_fts
                   JOIN notes n ON n.id = notes_fts.rowid
                   WHERE notes_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (match, limit),
            ).fetchall()
        hits = [
            SearchHit(
                note_id=int(r["id"]),
                ticker=r["ticker"],
                title=r["title"],
                snippet=r["snip"],
                score=float(r["rank"]),
            )
            for r in rows
        ]
        log.info("search.query", query=query, match=match, hits=len(hits))
        return hits
