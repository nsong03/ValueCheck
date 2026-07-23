"""Attribute service: key canonicalization, schema-on-write definitions,
value validation, and history/current-value retrieval (Phase 9)."""

from __future__ import annotations

import pytest

from equity.adapters.persistence.sqlite import SQLiteAttributeRepo
from equity.application.attribute_service import AttributeService, canonicalize_attribute_key
from equity.errors import NotFoundError, ValidationError

pytestmark = pytest.mark.integration


@pytest.fixture
def attributes(attribute_repo: SQLiteAttributeRepo) -> AttributeService:
    return AttributeService(attribute_repo)


class TestCanonicalization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("  Region ", "region"),
            ("Quality.Moat", "quality.moat"),
            ("quality moat", "quality-moat"),
            ("quality_moat", "quality-moat"),
            ("QUALITY.MANAGEMENT", "quality.management"),
            ("--edge--", "edge"),
            ("", ""),
        ],
    )
    def test_canonicalize_attribute_key(self, raw: str, expected: str) -> None:
        assert canonicalize_attribute_key(raw) == expected


class TestSetValue:
    def test_first_use_creates_definition_as_text(self, attributes: AttributeService) -> None:
        stored = attributes.set_value("demo", "Region", "china", source="note")
        assert stored.ticker == "DEMO"
        assert stored.key == "region"

        defs = {d.key: d for d in attributes.list_definitions()}
        assert defs["region"].value_type == "text"
        assert defs["region"].label == "Region"

    def test_scale_defaults_to_1_5(self, attributes: AttributeService) -> None:
        attributes.set_value("DEMO", "quality.moat", "4", source="note", value_type="scale")
        d = {d.key: d for d in attributes.list_definitions()}["quality.moat"]
        assert (d.scale_min, d.scale_max) == (1.0, 5.0)

    def test_scale_explicit_bounds(self, attributes: AttributeService) -> None:
        attributes.set_value(
            "DEMO",
            "headcount-band",
            "3",
            source="note",
            value_type="scale",
            scale_min=0,
            scale_max=3,
        )
        d = {d.key: d for d in attributes.list_definitions()}["headcount-band"]
        assert (d.scale_min, d.scale_max) == (0.0, 3.0)

    def test_scale_out_of_range_rejected(self, attributes: AttributeService) -> None:
        attributes.set_value("DEMO", "quality.moat", "4", source="note", value_type="scale")
        with pytest.raises(ValidationError):
            attributes.set_value("DEMO", "quality.moat", "9", source="grid")

    def test_number_requires_numeric(self, attributes: AttributeService) -> None:
        attributes.set_value("DEMO", "headcount", "500", source="note", value_type="number")
        with pytest.raises(ValidationError):
            attributes.set_value("DEMO", "headcount", "lots", source="grid")

    def test_existing_definition_type_is_authoritative(self, attributes: AttributeService) -> None:
        attributes.set_value("DEMO", "region", "china", source="note")  # creates as text
        # a later call claiming value_type="scale" is ignored — key already text
        attributes.set_value("DEMO", "region", "us", source="grid", value_type="scale")
        d = {d.key: d for d in attributes.list_definitions()}["region"]
        assert d.value_type == "text"

    def test_blank_ticker_rejected(self, attributes: AttributeService) -> None:
        with pytest.raises(ValidationError):
            attributes.set_value("   ", "region", "china", source="note")

    def test_blank_value_rejected(self, attributes: AttributeService) -> None:
        with pytest.raises(ValidationError):
            attributes.set_value("DEMO", "region", "   ", source="note")

    def test_blank_key_rejected(self, attributes: AttributeService) -> None:
        with pytest.raises(ValidationError):
            attributes.set_value("DEMO", "!!!", "x", source="note")

    def test_history_and_current(self, attributes: AttributeService) -> None:
        attributes.set_value("DEMO", "quality.moat", "3", source="note", value_type="scale")
        attributes.set_value("DEMO", "quality.moat", "4", source="grid")

        current = attributes.current_values("DEMO")
        assert current["quality.moat"].value == "4"

        history = attributes.history("DEMO", "quality.moat")
        assert [h.value for h in history] == ["4", "3"]


class TestUpdateDefinition:
    def test_curate_enum_with_colors(self, attributes: AttributeService) -> None:
        attributes.set_value("DEMO", "status", "good-company", source="grid")
        updated = attributes.update_definition(
            "status",
            allowed_values=["good-company", "avoid", "reanalyze-later"],
            colors={"good-company": "#22c55e", "avoid": "#ef4444"},
        )
        assert updated.allowed_values == ["good-company", "avoid", "reanalyze-later"]
        assert updated.colors == {"good-company": "#22c55e", "avoid": "#ef4444"}

    def test_promote_text_to_scale(self, attributes: AttributeService) -> None:
        attributes.set_value("DEMO", "conviction", "high", source="note")
        updated = attributes.update_definition(
            "conviction", value_type="scale", scale_min=1, scale_max=5
        )
        assert updated.value_type == "scale"
        # existing text value is untouched; only future writes are validated as scale
        assert attributes.current_values("DEMO")["conviction"].value == "high"

    def test_update_unknown_key_raises(self, attributes: AttributeService) -> None:
        with pytest.raises(NotFoundError):
            attributes.update_definition("ghost", label="Ghost")
