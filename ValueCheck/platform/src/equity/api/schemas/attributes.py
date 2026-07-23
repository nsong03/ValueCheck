"""Attribute DTOs: research facts (region, sector, quality scores, status)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from equity.domain.attributes import AttributeDefinition, AttributeSource, AttributeValue, ValueType


class AttributeDefinitionOut(BaseModel):
    key: str
    label: str
    value_type: ValueType
    scale_min: float | None = None
    scale_max: float | None = None
    allowed_values: list[str] | None = None
    colors: dict[str, str] | None = None

    @classmethod
    def from_domain(cls, d: AttributeDefinition) -> AttributeDefinitionOut:
        return cls(
            key=d.key,
            label=d.label,
            value_type=d.value_type,
            scale_min=d.scale_min,
            scale_max=d.scale_max,
            allowed_values=d.allowed_values,
            colors=d.colors,
        )


class AttributeDefinitionPatch(BaseModel):
    """Curate an existing key. Every field optional — only supplied fields change."""

    label: str | None = Field(default=None, min_length=1, max_length=100)
    value_type: ValueType | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    allowed_values: list[str] | None = None
    colors: dict[str, str] | None = None


class AttributeValueIn(BaseModel):
    """Set one attribute value. `value_type`/`label`/scale bounds only take
    effect the first time `key` is used — an existing key's type is
    authoritative (curate it via PATCH /attributes/definitions/{key})."""

    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=500)
    source: AttributeSource = "grid"
    note_id: int | None = None
    reason: str | None = Field(default=None, max_length=500)
    value_type: ValueType | None = None
    label: str | None = Field(default=None, max_length=100)
    scale_min: float | None = None
    scale_max: float | None = None


class AttributeValueOut(BaseModel):
    id: int
    ticker: str
    key: str
    value: str
    source: AttributeSource
    note_id: int | None
    reason: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, v: AttributeValue) -> AttributeValueOut:
        assert v.id is not None and v.created_at is not None
        return cls(
            id=v.id,
            ticker=v.ticker,
            key=v.key,
            value=v.value,
            source=v.source,
            note_id=v.note_id,
            reason=v.reason,
            created_at=v.created_at,
        )


class AttributeHistoryOut(BaseModel):
    ticker: str
    key: str
    values: list[AttributeValueOut]  # newest first
