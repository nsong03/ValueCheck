"""SQLite persistence adapter: migration runner + the four repositories.

Raw SQL over the stdlib sqlite3 module — no ORM (CLAUDE.md prime directive #7).
One short-lived connection per operation (single-user, local-first); foreign
keys ON; sqlite3.Row for name-based access. Storage failures surface as
`PersistenceError`; "not found" is None/False, never an exception.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from equity.adapters.persistence import mappers
from equity.domain.models import CompanyFinancials
from equity.domain.research import Note
from equity.domain.valuation import DCFResult, ValuationRecord
from equity.errors import PersistenceError
from equity.logging import get_logger

log = get_logger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _now() -> datetime:
    return datetime.now(UTC)


class SQLiteDatabase:
    """Connection factory + migration runner for one database file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise PersistenceError(f"sqlite failure: {exc}") from exc
        finally:
            conn.close()

    def migrate(self) -> list[str]:
        """Apply pending migrations in filename order. Returns those applied.

        Idempotent: applied versions are tracked in `schema_migrations`, and
        each migration runs inside the connection's transaction.
        """
        applied: list[str] = []
        with self.connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                       version INTEGER PRIMARY KEY,
                       name TEXT NOT NULL,
                       applied_at TEXT NOT NULL)"""
            )
            done = {
                int(r["version"]) for r in conn.execute("SELECT version FROM schema_migrations")
            }
            for script in sorted(_MIGRATIONS_DIR.glob("*.sql")):
                version = int(script.stem.split("_", 1)[0])
                if version in done:
                    continue
                # executescript() implicitly commits first; opening an explicit
                # transaction inside the script keeps the schema changes AND the
                # version record atomic (committed together at context exit).
                conn.executescript("BEGIN;\n" + script.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, script.stem, _now().isoformat()),
                )
                applied.append(script.stem)
        if applied:
            log.info("sqlite.migrated", path=str(self.path), applied=applied)
        return applied


# --------------------------------------------------------------------------- #
# repositories
# --------------------------------------------------------------------------- #
class SQLiteCompanyRepo:
    def __init__(self, db: SQLiteDatabase) -> None:
        self._db = db

    def save(self, fin: CompanyFinancials) -> None:
        row = mappers.company_row(fin, fetched_at=_now())
        with self._db.connection() as conn:
            conn.execute(
                """INSERT INTO companies (ticker, name, sector, industry, sic, total_debt,
                                          cash, shares_out, price, beta, fetched_at)
                   VALUES (:ticker, :name, :sector, :industry, :sic, :total_debt,
                           :cash, :shares_out, :price, :beta, :fetched_at)
                   ON CONFLICT(ticker) DO UPDATE SET
                       name=excluded.name, sector=excluded.sector,
                       industry=excluded.industry, sic=excluded.sic,
                       total_debt=excluded.total_debt, cash=excluded.cash,
                       shares_out=excluded.shares_out, price=excluded.price,
                       beta=excluded.beta, fetched_at=excluded.fetched_at""",
                row,
            )
            # facts + sources are replaced wholesale: simplest correct upsert
            conn.execute("DELETE FROM financial_facts WHERE ticker = ?", (fin.ticker,))
            conn.executemany(
                "INSERT INTO financial_facts (ticker, fiscal_year, metric, value)"
                " VALUES (?, ?, ?, ?)",
                mappers.fact_rows(fin),
            )
            conn.execute("DELETE FROM source_links WHERE ticker = ?", (fin.ticker,))
            conn.executemany(
                "INSERT INTO source_links (ticker, position, label, url, accession)"
                " VALUES (?, ?, ?, ?, ?)",
                mappers.source_rows(fin),
            )

    def get(self, ticker: str) -> CompanyFinancials | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM companies WHERE ticker = ?", (ticker,)).fetchone()
            if row is None:
                return None
            facts = conn.execute(
                "SELECT fiscal_year, metric, value FROM financial_facts WHERE ticker = ?",
                (ticker,),
            ).fetchall()
            sources = conn.execute(
                "SELECT label, url, accession FROM source_links WHERE ticker = ? ORDER BY position",
                (ticker,),
            ).fetchall()
        return mappers.build_company(row, facts, sources)

    def list_tickers(self) -> list[str]:
        with self._db.connection() as conn:
            rows = conn.execute("SELECT ticker FROM companies ORDER BY ticker").fetchall()
        return [r["ticker"] for r in rows]

    def delete(self, ticker: str) -> bool:
        with self._db.connection() as conn:
            cur = conn.execute("DELETE FROM companies WHERE ticker = ?", (ticker,))
        return cur.rowcount > 0


class SQLiteValuationRepo:
    def __init__(self, db: SQLiteDatabase) -> None:
        self._db = db

    def save(self, result: DCFResult) -> ValuationRecord:
        row = mappers.valuation_row(result, created_at=_now())
        with self._db.connection() as conn:
            cur = conn.execute(
                """INSERT INTO valuations (ticker, created_at, wacc, enterprise_value,
                                           equity_value, fair_value_per_share, upside,
                                           assumptions_json, projection_json, warnings_json)
                   VALUES (:ticker, :created_at, :wacc, :enterprise_value, :equity_value,
                           :fair_value_per_share, :upside, :assumptions_json,
                           :projection_json, :warnings_json)""",
                row,
            )
            stored = conn.execute(
                "SELECT * FROM valuations WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return mappers.build_valuation_record(stored)

    def get(self, valuation_id: int) -> ValuationRecord | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM valuations WHERE id = ?", (valuation_id,)).fetchone()
        return mappers.build_valuation_record(row) if row is not None else None

    def list_for(self, ticker: str) -> list[ValuationRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM valuations WHERE ticker = ? ORDER BY created_at DESC, id DESC",
                (ticker,),
            ).fetchall()
        return [mappers.build_valuation_record(r) for r in rows]


class SQLiteNoteRepo:
    def __init__(self, db: SQLiteDatabase) -> None:
        self._db = db

    def save(self, note: Note) -> Note:
        now = _now()
        with self._db.connection() as conn:
            if note.id is None:
                cur = conn.execute(
                    "INSERT INTO notes (ticker, title, body, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (note.ticker, note.title, note.body, now.isoformat(), now.isoformat()),
                )
                note_id = int(cur.lastrowid or 0)
            else:
                cur = conn.execute(
                    "UPDATE notes SET ticker = ?, title = ?, body = ?, updated_at = ? WHERE id = ?",
                    (note.ticker, note.title, note.body, now.isoformat(), note.id),
                )
                if cur.rowcount == 0:
                    raise PersistenceError(f"note {note.id} does not exist")
                note_id = note.id
            self._replace_tags(conn, note_id, note.tags)
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
            tags = self._tags_for(conn, note_id)
        return mappers.build_note(row, tags)

    def get(self, note_id: int) -> Note | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
            if row is None:
                return None
            tags = self._tags_for(conn, note_id)
        return mappers.build_note(row, tags)

    def list_for(self, ticker: str) -> list[Note]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM notes WHERE ticker = ? ORDER BY created_at DESC, id DESC",
                (ticker,),
            ).fetchall()
            notes = [mappers.build_note(r, self._tags_for(conn, int(r["id"]))) for r in rows]
        return notes

    def delete(self, note_id: int) -> bool:
        with self._db.connection() as conn:
            cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        return cur.rowcount > 0

    @staticmethod
    def _replace_tags(conn: sqlite3.Connection, note_id: int, tags: list[str]) -> None:
        conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
        for tag in tags:
            conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
            conn.execute(
                "INSERT OR IGNORE INTO note_tags (note_id, tag_id)"
                " SELECT ?, id FROM tags WHERE name = ?",
                (note_id, tag),
            )

    @staticmethod
    def _tags_for(conn: sqlite3.Connection, note_id: int) -> list[str]:
        rows = conn.execute(
            """SELECT t.name FROM tags t
               JOIN note_tags nt ON nt.tag_id = t.id
               WHERE nt.note_id = ? ORDER BY t.name""",
            (note_id,),
        ).fetchall()
        return [r["name"] for r in rows]


class SQLiteTagRepo:
    def __init__(self, db: SQLiteDatabase) -> None:
        self._db = db

    def all_tags(self) -> list[str]:
        with self._db.connection() as conn:
            rows = conn.execute(
                """SELECT DISTINCT t.name FROM tags t
                   JOIN note_tags nt ON nt.tag_id = t.id
                   ORDER BY t.name"""
            ).fetchall()
        return [r["name"] for r in rows]

    def merge(self, source: str, target: str) -> int:
        """Fold `source` into `target` in one transaction (see TagRepo port)."""
        with self._db.connection() as conn:
            src = conn.execute("SELECT id FROM tags WHERE name = ?", (source,)).fetchone()
            if src is None:
                return 0
            src_id = int(src["id"])
            affected = conn.execute(
                "SELECT COUNT(DISTINCT note_id) AS n FROM note_tags WHERE tag_id = ?",
                (src_id,),
            ).fetchone()["n"]
            if affected:
                conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (target,))
                dst_id = int(
                    conn.execute("SELECT id FROM tags WHERE name = ?", (target,)).fetchone()["id"]
                )
                # retag; OR IGNORE covers notes already carrying the target
                conn.execute(
                    "INSERT OR IGNORE INTO note_tags (note_id, tag_id)"
                    " SELECT note_id, ? FROM note_tags WHERE tag_id = ?",
                    (dst_id, src_id),
                )
                conn.execute("DELETE FROM note_tags WHERE tag_id = ?", (src_id,))
            conn.execute("DELETE FROM tags WHERE id = ?", (src_id,))
        return int(affected)
