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
from equity.domain.analysis import Analysis
from equity.domain.attributes import AttributeDefinition, AttributeValue
from equity.domain.models import CompanyFinancials
from equity.domain.references import Reference
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
        links_json = mappers.links_to_json(note.links)
        with self._db.connection() as conn:
            if note.id is None:
                cur = conn.execute(
                    """INSERT INTO notes
                           (ticker, reference_id, analysis_id, title, body,
                            links_json, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        note.ticker,
                        note.reference_id,
                        note.analysis_id,
                        note.title,
                        note.body,
                        links_json,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                note_id = int(cur.lastrowid or 0)
            else:
                cur = conn.execute(
                    """UPDATE notes SET title = ?, body = ?, links_json = ?, updated_at = ?
                       WHERE id = ?""",
                    (note.title, note.body, links_json, now.isoformat(), note.id),
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

    def list_for_reference(self, reference_id: int) -> list[Note]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM notes WHERE reference_id = ? ORDER BY created_at DESC, id DESC",
                (reference_id,),
            ).fetchall()
            notes = [mappers.build_note(r, self._tags_for(conn, int(r["id"]))) for r in rows]
        return notes

    def list_for_analysis(self, analysis_id: int) -> list[Note]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM notes WHERE analysis_id = ? ORDER BY created_at DESC, id DESC",
                (analysis_id,),
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


class SQLiteAttributeRepo:
    """Implements ports.repository.AttributeRepo.

    "Current value" is derived from the append-only history table with a
    window function (`ROW_NUMBER() OVER (PARTITION BY key ORDER BY
    created_at DESC)`), not a second table — nothing to keep in sync.
    """

    def __init__(self, db: SQLiteDatabase) -> None:
        self._db = db

    # -- definitions -----------------------------------------------------------
    def get_definition(self, key: str) -> AttributeDefinition | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM attribute_definitions WHERE key = ?", (key,)
            ).fetchone()
        return mappers.build_definition(row) if row is not None else None

    def upsert_definition(self, definition: AttributeDefinition) -> AttributeDefinition:
        row = mappers.definition_row(definition, created_at=_now())
        with self._db.connection() as conn:
            conn.execute(
                """INSERT INTO attribute_definitions
                       (key, label, value_type, scale_min, scale_max,
                        allowed_values_json, colors_json, created_at)
                   VALUES (:key, :label, :value_type, :scale_min, :scale_max,
                           :allowed_values_json, :colors_json, :created_at)
                   ON CONFLICT(key) DO UPDATE SET
                       label=excluded.label, value_type=excluded.value_type,
                       scale_min=excluded.scale_min, scale_max=excluded.scale_max,
                       allowed_values_json=excluded.allowed_values_json,
                       colors_json=excluded.colors_json""",
                row,
            )
            stored = conn.execute(
                "SELECT * FROM attribute_definitions WHERE key = ?", (definition.key,)
            ).fetchone()
        return mappers.build_definition(stored)

    def list_definitions(self) -> list[AttributeDefinition]:
        with self._db.connection() as conn:
            rows = conn.execute("SELECT * FROM attribute_definitions ORDER BY key").fetchall()
        return [mappers.build_definition(r) for r in rows]

    # -- values ------------------------------------------------------------------
    def append_value(self, value: AttributeValue) -> AttributeValue:
        row = mappers.attribute_value_row(value, created_at=_now())
        with self._db.connection() as conn:
            cur = conn.execute(
                """INSERT INTO company_attribute_history
                       (ticker, key, value, source, note_id, reason, created_at)
                   VALUES (:ticker, :key, :value, :source, :note_id, :reason, :created_at)""",
                row,
            )
            stored = conn.execute(
                "SELECT * FROM company_attribute_history WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return mappers.build_attribute_value(stored)

    def history_for(self, ticker: str, key: str) -> list[AttributeValue]:
        with self._db.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM company_attribute_history
                   WHERE ticker = ? AND key = ?
                   ORDER BY created_at DESC, id DESC""",
                (ticker, key),
            ).fetchall()
        return [mappers.build_attribute_value(r) for r in rows]

    def current_for(self, ticker: str) -> dict[str, AttributeValue]:
        with self._db.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM (
                       SELECT h.*, ROW_NUMBER() OVER (
                           PARTITION BY h.key ORDER BY h.created_at DESC, h.id DESC
                       ) AS rn
                       FROM company_attribute_history h
                       WHERE h.ticker = ?
                   ) WHERE rn = 1""",
                (ticker,),
            ).fetchall()
        return {r["key"]: mappers.build_attribute_value(r) for r in rows}


class SQLiteReferenceRepo:
    """Implements ports.repository.ReferenceRepo (the knowledge library)."""

    def __init__(self, db: SQLiteDatabase) -> None:
        self._db = db

    def save(self, reference: Reference) -> Reference:
        row = mappers.reference_row(reference, added_at=_now())
        with self._db.connection() as conn:
            if reference.id is None:
                cur = conn.execute(
                    """INSERT INTO reference_items
                           (kind, title, location, collection, origin, added_at)
                       VALUES (:kind, :title, :location, :collection, :origin, :added_at)""",
                    row,
                )
                reference_id = int(cur.lastrowid or 0)
            else:
                conn.execute(
                    """UPDATE reference_items
                           SET kind = :kind, title = :title, location = :location,
                               collection = :collection, origin = :origin
                       WHERE id = :id""",
                    {**row, "id": reference.id},
                )
                reference_id = reference.id
            stored = conn.execute(
                "SELECT * FROM reference_items WHERE id = ?", (reference_id,)
            ).fetchone()
        return mappers.build_reference(stored)

    def get(self, reference_id: int) -> Reference | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM reference_items WHERE id = ?", (reference_id,)
            ).fetchone()
        return mappers.build_reference(row) if row is not None else None

    def get_by_location(self, location: str) -> Reference | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM reference_items WHERE location = ?", (location,)
            ).fetchone()
        return mappers.build_reference(row) if row is not None else None

    def list_all(self) -> list[Reference]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM reference_items ORDER BY collection, title"
            ).fetchall()
        return [mappers.build_reference(r) for r in rows]

    def delete(self, reference_id: int) -> bool:
        with self._db.connection() as conn:
            cur = conn.execute("DELETE FROM reference_items WHERE id = ?", (reference_id,))
        return cur.rowcount > 0


class SQLiteAnalysisRepo:
    """Implements ports.repository.AnalysisRepo (the balcony)."""

    def __init__(self, db: SQLiteDatabase) -> None:
        self._db = db

    def save(self, analysis: Analysis) -> Analysis:
        now = _now()
        with self._db.connection() as conn:
            if analysis.id is None:
                cur = conn.execute(
                    """INSERT INTO analyses (kind, title, summary, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        analysis.kind,
                        analysis.title,
                        analysis.summary,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                analysis_id = int(cur.lastrowid or 0)
            else:
                cur = conn.execute(
                    """UPDATE analyses SET kind = ?, title = ?, summary = ?, updated_at = ?
                       WHERE id = ?""",
                    (analysis.kind, analysis.title, analysis.summary, now.isoformat(), analysis.id),
                )
                if cur.rowcount == 0:
                    raise PersistenceError(f"analysis {analysis.id} does not exist")
                analysis_id = analysis.id
            row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        return mappers.build_analysis(row)

    def get(self, analysis_id: int) -> Analysis | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        return mappers.build_analysis(row) if row is not None else None

    def list_all(self) -> list[Analysis]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM analyses ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [mappers.build_analysis(r) for r in rows]

    def delete(self, analysis_id: int) -> bool:
        with self._db.connection() as conn:
            cur = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        return cur.rowcount > 0

    # -- company constituents -----------------------------------------------
    def add_company(self, analysis_id: int, ticker: str) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO analysis_companies (analysis_id, ticker) VALUES (?, ?)",
                (analysis_id, ticker),
            )

    def remove_company(self, analysis_id: int, ticker: str) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "DELETE FROM analysis_companies WHERE analysis_id = ? AND ticker = ?",
                (analysis_id, ticker),
            )

    def list_companies(self, analysis_id: int) -> list[str]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT ticker FROM analysis_companies WHERE analysis_id = ? ORDER BY ticker",
                (analysis_id,),
            ).fetchall()
        return [r["ticker"] for r in rows]

    def list_for_company(self, ticker: str) -> list[Analysis]:
        with self._db.connection() as conn:
            rows = conn.execute(
                """SELECT a.* FROM analyses a
                   JOIN analysis_companies ac ON ac.analysis_id = a.id
                   WHERE ac.ticker = ?
                   ORDER BY a.created_at DESC, a.id DESC""",
                (ticker,),
            ).fetchall()
        return [mappers.build_analysis(r) for r in rows]

    # -- reference constituents ----------------------------------------------
    def add_reference(self, analysis_id: int, reference_id: int) -> None:
        with self._db.connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO analysis_references (analysis_id, reference_id)
                   VALUES (?, ?)""",
                (analysis_id, reference_id),
            )

    def remove_reference(self, analysis_id: int, reference_id: int) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "DELETE FROM analysis_references WHERE analysis_id = ? AND reference_id = ?",
                (analysis_id, reference_id),
            )

    def list_references(self, analysis_id: int) -> list[int]:
        with self._db.connection() as conn:
            rows = conn.execute(
                """SELECT reference_id FROM analysis_references
                   WHERE analysis_id = ? ORDER BY reference_id""",
                (analysis_id,),
            ).fetchall()
        return [int(r["reference_id"]) for r in rows]

    def list_for_reference(self, reference_id: int) -> list[Analysis]:
        with self._db.connection() as conn:
            rows = conn.execute(
                """SELECT a.* FROM analyses a
                   JOIN analysis_references ar ON ar.analysis_id = a.id
                   WHERE ar.reference_id = ?
                   ORDER BY a.created_at DESC, a.id DESC""",
                (reference_id,),
            ).fetchall()
        return [mappers.build_analysis(r) for r in rows]

    # -- analysis <-> analysis links ------------------------------------------
    def add_link(self, analysis_id: int, linked_analysis_id: int) -> None:
        with self._db.connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO analysis_links (analysis_id, linked_analysis_id)
                   VALUES (?, ?)""",
                (analysis_id, linked_analysis_id),
            )

    def remove_link(self, analysis_id: int, linked_analysis_id: int) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "DELETE FROM analysis_links WHERE analysis_id = ? AND linked_analysis_id = ?",
                (analysis_id, linked_analysis_id),
            )

    def list_links(self, analysis_id: int) -> list[int]:
        with self._db.connection() as conn:
            rows = conn.execute(
                """SELECT linked_analysis_id FROM analysis_links
                   WHERE analysis_id = ? ORDER BY linked_analysis_id""",
                (analysis_id,),
            ).fetchall()
        return [int(r["linked_analysis_id"]) for r in rows]
