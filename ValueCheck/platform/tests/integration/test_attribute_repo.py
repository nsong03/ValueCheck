"""Attribute repository round-trips: definitions, append-only history, and
the latest-value derivation (Phase 9)."""

from __future__ import annotations

import pytest

from equity.adapters.persistence.sqlite import SQLiteAttributeRepo, SQLiteNoteRepo
from equity.domain.attributes import AttributeDefinition, AttributeValue
from equity.domain.research import Note

pytestmark = pytest.mark.integration


class TestDefinitions:
    def test_upsert_creates_then_updates(self, attribute_repo: SQLiteAttributeRepo) -> None:
        created = attribute_repo.upsert_definition(
            AttributeDefinition(
                key="quality.moat", label="Moat", value_type="scale", scale_min=1, scale_max=5
            )
        )
        assert created.label == "Moat"

        updated = attribute_repo.upsert_definition(
            AttributeDefinition(
                key="quality.moat",
                label="Moat Strength",
                value_type="scale",
                scale_min=0,
                scale_max=10,
            )
        )
        assert updated.label == "Moat Strength"
        assert updated.scale_max == 10
        assert attribute_repo.get_definition("quality.moat") == updated

    def test_get_missing_returns_none(self, attribute_repo: SQLiteAttributeRepo) -> None:
        assert attribute_repo.get_definition("ghost") is None

    def test_list_definitions_sorted(self, attribute_repo: SQLiteAttributeRepo) -> None:
        attribute_repo.upsert_definition(AttributeDefinition(key="region", label="Region"))
        attribute_repo.upsert_definition(AttributeDefinition(key="moat", label="Moat"))
        assert [d.key for d in attribute_repo.list_definitions()] == ["moat", "region"]

    def test_definition_with_allowed_values_and_colors_round_trips(
        self, attribute_repo: SQLiteAttributeRepo
    ) -> None:
        stored = attribute_repo.upsert_definition(
            AttributeDefinition(
                key="status",
                label="Status",
                allowed_values=["good-company", "avoid"],
                colors={"good-company": "#22c55e", "avoid": "#ef4444"},
            )
        )
        loaded = attribute_repo.get_definition("status")
        assert loaded == stored
        assert loaded is not None
        assert loaded.allowed_values == ["good-company", "avoid"]
        assert loaded.colors == {"good-company": "#22c55e", "avoid": "#ef4444"}


class TestHistoryAndCurrent:
    def test_append_assigns_identity(self, attribute_repo: SQLiteAttributeRepo) -> None:
        attribute_repo.upsert_definition(AttributeDefinition(key="region", label="Region"))
        stored = attribute_repo.append_value(
            AttributeValue(ticker="DEMO", key="region", value="china", source="note")
        )
        assert stored.id is not None
        assert stored.created_at is not None

    def test_current_is_latest_per_key(self, attribute_repo: SQLiteAttributeRepo) -> None:
        attribute_repo.upsert_definition(
            AttributeDefinition(key="quality.moat", label="Moat", value_type="scale")
        )
        attribute_repo.append_value(
            AttributeValue(ticker="DEMO", key="quality.moat", value="3", source="note")
        )
        attribute_repo.append_value(
            AttributeValue(ticker="DEMO", key="quality.moat", value="4", source="grid")
        )
        current = attribute_repo.current_for("DEMO")
        assert current["quality.moat"].value == "4"
        assert current["quality.moat"].source == "grid"

    def test_current_scoped_per_ticker(self, attribute_repo: SQLiteAttributeRepo) -> None:
        attribute_repo.upsert_definition(AttributeDefinition(key="region", label="Region"))
        attribute_repo.append_value(
            AttributeValue(ticker="AAPL", key="region", value="us", source="note")
        )
        attribute_repo.append_value(
            AttributeValue(ticker="TSM", key="region", value="taiwan", source="note")
        )
        assert attribute_repo.current_for("AAPL")["region"].value == "us"
        assert attribute_repo.current_for("TSM")["region"].value == "taiwan"

    def test_history_newest_first(self, attribute_repo: SQLiteAttributeRepo) -> None:
        attribute_repo.upsert_definition(AttributeDefinition(key="region", label="Region"))
        v1 = attribute_repo.append_value(
            AttributeValue(ticker="DEMO", key="region", value="us", source="note")
        )
        v2 = attribute_repo.append_value(
            AttributeValue(ticker="DEMO", key="region", value="china", source="grid")
        )
        history = attribute_repo.history_for("DEMO", "region")
        assert [h.id for h in history] == [v2.id, v1.id]

    def test_no_history_is_empty(self, attribute_repo: SQLiteAttributeRepo) -> None:
        assert attribute_repo.history_for("DEMO", "region") == []
        assert attribute_repo.current_for("DEMO") == {}

    def test_deleting_note_nulls_note_id_not_history(
        self, attribute_repo: SQLiteAttributeRepo, note_repo: SQLiteNoteRepo
    ) -> None:
        attribute_repo.upsert_definition(AttributeDefinition(key="region", label="Region"))
        note = note_repo.save(Note(ticker="DEMO", title="t", body=""))
        assert note.id is not None
        stored = attribute_repo.append_value(
            AttributeValue(ticker="DEMO", key="region", value="us", source="note", note_id=note.id)
        )
        note_repo.delete(note.id)

        history = attribute_repo.history_for("DEMO", "region")
        assert len(history) == 1
        assert history[0].id == stored.id
        assert history[0].note_id is None  # provenance link cleared, fact preserved
