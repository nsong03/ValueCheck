"""Migrations apply cleanly from empty, idempotently, and match schema.sql."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from equity.adapters.persistence.sqlite import SQLiteDatabase

pytestmark = pytest.mark.integration

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "src/equity/adapters/persistence/schema.sql"

EXPECTED_TABLES = {
    "schema_migrations",
    "companies",
    "financial_facts",
    "source_links",
    "valuations",
    "notes",
    "tags",
    "note_tags",
    # FTS5 (0002): the virtual table + its shadow tables
    "notes_fts",
    "notes_fts_data",
    "notes_fts_idx",
    "notes_fts_docsize",
    "notes_fts_config",
}


def table_columns(conn: sqlite3.Connection) -> dict[str, list[tuple[str, str]]]:
    """{table: [(column, declared_type), ...]} for every non-internal table."""
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {t: [(r[1], r[2]) for r in conn.execute(f"PRAGMA table_info({t})")] for t in tables}


def test_migrate_from_empty(tmp_path: Path) -> None:
    db = SQLiteDatabase(tmp_path / "fresh.db")
    applied = db.migrate()
    assert applied == ["0001_initial", "0002_search"]
    with db.connection() as conn:
        names = set(table_columns(conn))
    assert names == EXPECTED_TABLES


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = SQLiteDatabase(tmp_path / "fresh.db")
    assert db.migrate() == ["0001_initial", "0002_search"]
    assert db.migrate() == []  # second run: nothing to do


def test_migrate_applies_only_pending(tmp_path: Path) -> None:
    """A db already at 0001 gets exactly 0002 (upgrade path, not rebuild)."""
    path = tmp_path / "upgrade.db"
    legacy = sqlite3.connect(path)
    migrations = Path("src/equity/adapters/persistence/migrations")
    legacy.executescript(
        "CREATE TABLE schema_migrations ("
        " version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL);"
    )
    legacy.executescript((migrations / "0001_initial.sql").read_text(encoding="utf-8"))
    legacy.execute(
        "INSERT INTO schema_migrations (version, name, applied_at)"
        " VALUES (1, '0001_initial', '2026-01-01T00:00:00')"
    )
    # a pre-existing note must get backfilled into the new index
    legacy.execute(
        "INSERT INTO notes (ticker, title, body, created_at, updated_at)"
        " VALUES ('OLD', 'legacy note', 'chip shortage thesis', 't', 't')"
    )
    legacy.commit()
    legacy.close()

    db = SQLiteDatabase(path)
    assert db.migrate() == ["0002_search"]
    with db.connection() as conn:
        hit = conn.execute(
            "SELECT rowid FROM notes_fts WHERE notes_fts MATCH 'shortage'"
        ).fetchone()
    assert hit is not None  # backfill indexed the legacy row


def test_migrations_match_canonical_schema(tmp_path: Path) -> None:
    """Guard against drift: migrations must build exactly schema.sql."""
    migrated = SQLiteDatabase(tmp_path / "migrated.db")
    migrated.migrate()

    canonical = sqlite3.connect(tmp_path / "canonical.db")
    canonical.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))

    with migrated.connection() as conn:
        via_migrations = table_columns(conn)
    via_schema = table_columns(canonical)
    canonical.close()

    # schema_migrations differs by construction path; compare the rest exactly
    via_migrations.pop("schema_migrations")
    via_schema.pop("schema_migrations")
    assert via_migrations == via_schema
