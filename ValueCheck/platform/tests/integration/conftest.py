"""Integration fixtures: a migrated temp SQLite database per test."""

from __future__ import annotations

from pathlib import Path

import pytest

from equity.adapters.persistence.sqlite import (
    SQLiteCompanyRepo,
    SQLiteDatabase,
    SQLiteNoteRepo,
    SQLiteTagRepo,
    SQLiteValuationRepo,
)


@pytest.fixture
def db(tmp_path: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "test.db")
    database.migrate()
    return database


@pytest.fixture
def company_repo(db: SQLiteDatabase) -> SQLiteCompanyRepo:
    return SQLiteCompanyRepo(db)


@pytest.fixture
def valuation_repo(db: SQLiteDatabase) -> SQLiteValuationRepo:
    return SQLiteValuationRepo(db)


@pytest.fixture
def note_repo(db: SQLiteDatabase) -> SQLiteNoteRepo:
    return SQLiteNoteRepo(db)


@pytest.fixture
def tag_repo(db: SQLiteDatabase) -> SQLiteTagRepo:
    return SQLiteTagRepo(db)
