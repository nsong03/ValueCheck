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
    # research attributes (0003)
    "attribute_definitions",
    "company_attribute_history",
    # knowledge library (0004)
    "reference_items",
    # the balcony (0005)
    "analyses",
    "analysis_companies",
    "analysis_references",
    "analysis_links",
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


EXPECTED_MIGRATIONS = [
    "0001_initial",
    "0002_search",
    "0003_attributes",
    "0004_reference_library",
    "0005_analysis",
]


def test_migrate_from_empty(tmp_path: Path) -> None:
    db = SQLiteDatabase(tmp_path / "fresh.db")
    applied = db.migrate()
    assert applied == EXPECTED_MIGRATIONS
    with db.connection() as conn:
        names = set(table_columns(conn))
    assert names == EXPECTED_TABLES


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = SQLiteDatabase(tmp_path / "fresh.db")
    assert db.migrate() == EXPECTED_MIGRATIONS
    assert db.migrate() == []  # second run: nothing to do


def test_migrate_applies_only_pending(tmp_path: Path) -> None:
    """A db already at 0001 gets exactly what's pending (upgrade, not rebuild)."""
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
    assert db.migrate() == [
        "0002_search",
        "0003_attributes",
        "0004_reference_library",
        "0005_analysis",
    ]
    with db.connection() as conn:
        hit = conn.execute(
            "SELECT rowid FROM notes_fts WHERE notes_fts MATCH 'shortage'"
        ).fetchone()
        survived = conn.execute(
            "SELECT ticker, reference_id, analysis_id FROM notes WHERE ticker = 'OLD'"
        ).fetchone()
    assert hit is not None  # backfill indexed the legacy row
    assert tuple(survived) == ("OLD", None, None)  # both rebuilds preserved the legacy row


def test_notes_rebuild_preserves_tags_and_attribute_provenance(tmp_path: Path) -> None:
    """Regression test: 0004 and 0005 each rebuild `notes` (drop + recreate)
    to widen its subject column(s). With `PRAGMA foreign_keys = ON`, SQLite
    fires a dropped table's children's ON DELETE actions even for a same-
    transaction drop+recreate, not just a real DELETE — so naively dropping
    `notes` silently deletes every `note_tags` row (ON DELETE CASCADE) and
    nulls every `company_attribute_history.note_id` (ON DELETE SET NULL).
    Both migrations must back up and restore these before/after the drop.
    """
    path = tmp_path / "upgrade.db"
    migrations = Path("src/equity/adapters/persistence/migrations")
    legacy = sqlite3.connect(path)
    legacy.execute("PRAGMA foreign_keys = ON")
    legacy.executescript(
        "CREATE TABLE schema_migrations ("
        " version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL);"
    )
    for name in ("0001_initial", "0002_search", "0003_attributes"):
        legacy.executescript((migrations / f"{name}.sql").read_text(encoding="utf-8"))
        version = int(name.split("_", 1)[0])
        legacy.execute(
            "INSERT INTO schema_migrations (version, name, applied_at)"
            " VALUES (?, ?, '2026-01-01T00:00:00')",
            (version, name),
        )

    # a note carrying a tag, plus an attribute value whose provenance points
    # back at that note — both must survive the two notes-rebuilds below
    legacy.execute(
        "INSERT INTO notes (id, ticker, title, body, created_at, updated_at)"
        " VALUES (1, 'OLD', 'legacy note', 'body', 't', 't')"
    )
    legacy.execute("INSERT INTO tags (id, name) VALUES (1, 'moat')")
    legacy.execute("INSERT INTO note_tags (note_id, tag_id) VALUES (1, 1)")
    legacy.execute(
        "INSERT INTO attribute_definitions (key, label, value_type, created_at)"
        " VALUES ('region', 'Region', 'text', 't')"
    )
    legacy.execute(
        "INSERT INTO company_attribute_history"
        " (ticker, key, value, source, note_id, created_at)"
        " VALUES ('OLD', 'region', 'us', 'note', 1, 't')"
    )
    legacy.commit()
    legacy.close()

    db = SQLiteDatabase(path)
    assert db.migrate() == ["0004_reference_library", "0005_analysis"]
    with db.connection() as conn:
        tags = conn.execute(
            "SELECT t.name FROM tags t JOIN note_tags nt ON nt.tag_id = t.id WHERE nt.note_id = 1"
        ).fetchall()
        provenance = conn.execute(
            "SELECT note_id FROM company_attribute_history WHERE ticker = 'OLD' AND key = 'region'"
        ).fetchone()
    assert [r["name"] for r in tags] == ["moat"]  # not silently deleted
    assert provenance["note_id"] == 1  # not silently nulled


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
