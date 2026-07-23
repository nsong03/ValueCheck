"""Attribute service: typed, namespaced facts about a company (region,
custom sector, quality scores, status), entered either alongside a note or
as a direct edit from the screener grid — with full history (Phase 9).

Key canonicalization mirrors tag canonicalization (equity.application.
research_service) but keeps '.' as a namespace separator, so "Quality.Moat"
and "quality moat" both normalize to "quality.moat" while "quality.moat" and
"quality.management" stay distinct dimensions. Definitions are schema-ON-
WRITE: the first `set_value()` for a new key creates its definition (default
type "text"); an existing key's type is authoritative from then on. Use
`update_definition()` to curate a key later — promote it to a scale, or
attach an enum's allowed values/colors (e.g. `status`).
"""

from __future__ import annotations

import re

from equity.domain.attributes import (
    AttributeDefinition,
    AttributeSource,
    AttributeValue,
    ValueType,
)
from equity.errors import NotFoundError, ValidationError
from equity.logging import get_logger
from equity.ports.repository import AttributeRepo

log = get_logger(__name__)

_SEPARATORS = re.compile(r"[\s_/]+")
_DISALLOWED = re.compile(r"[^a-z0-9.-]")
_RUNS = re.compile(r"[.-]{2,}")

_DEFAULT_SCALE = (1.0, 5.0)


def canonicalize_attribute_key(raw: str) -> str:
    """Lowercase, kebab-case, dot-namespaced canonical key.

    "Quality Moat" -> "quality-moat"; "Quality.Moat" -> "quality.moat" (the
    dot is preserved as a namespace separator, unlike a plain tag).
    """
    key = raw.strip().lower()
    key = _SEPARATORS.sub("-", key)
    key = _DISALLOWED.sub("", key)
    key = _RUNS.sub(lambda m: m.group(0)[0], key)
    return key.strip(".-")


def _humanize(key: str) -> str:
    """Default label for an implicitly-created definition, e.g.
    "quality.moat" -> "Quality Moat"."""
    return key.replace(".", " ").replace("-", " ").title()


class AttributeService:
    def __init__(self, attributes: AttributeRepo) -> None:
        self._attributes = attributes

    # -- values -----------------------------------------------------------------
    def set_value(
        self,
        ticker: str,
        key: str,
        value: str,
        *,
        source: AttributeSource,
        note_id: int | None = None,
        reason: str | None = None,
        value_type: ValueType | None = None,
        label: str | None = None,
        scale_min: float | None = None,
        scale_max: float | None = None,
    ) -> AttributeValue:
        """Record one value for (ticker, key).

        Creates the definition on first use of `key` (`value_type` defaults
        to "text"; a "scale" with no bounds given defaults to 1-5). An
        existing definition's type is authoritative — passing a mismatched
        `value_type` on a later call is silently ignored (use
        `update_definition` to change a key's type deliberately).
        """
        ticker = ticker.upper().strip()
        if not ticker:
            raise ValidationError("attribute requires a ticker")
        canonical_key = canonicalize_attribute_key(key)
        if not canonical_key:
            raise ValidationError("attribute key must be non-empty after canonicalization")

        definition = self._attributes.get_definition(canonical_key)
        if definition is None:
            vt: ValueType = value_type or "text"
            lo, hi = self._scale_bounds(vt, scale_min, scale_max)
            definition = self._attributes.upsert_definition(
                AttributeDefinition(
                    key=canonical_key,
                    label=(label or _humanize(canonical_key)).strip(),
                    value_type=vt,
                    scale_min=lo,
                    scale_max=hi,
                )
            )
            log.info("attribute.definition_created", key=canonical_key, value_type=vt)

        text = value.strip()
        if not text:
            raise ValidationError(f"attribute {canonical_key!r} requires a non-empty value")
        self._validate_value(definition, text)

        stored = self._attributes.append_value(
            AttributeValue(
                ticker=ticker,
                key=canonical_key,
                value=text,
                source=source,
                note_id=note_id,
                reason=reason,
            )
        )
        log.info("attribute.set", ticker=ticker, key=canonical_key, source=source)
        return stored

    def history(self, ticker: str, key: str) -> list[AttributeValue]:
        """Every value ever recorded for (ticker, key), newest first."""
        return self._attributes.history_for(ticker.upper().strip(), canonicalize_attribute_key(key))

    def current_values(self, ticker: str) -> dict[str, AttributeValue]:
        """The latest value per key for one company."""
        return self._attributes.current_for(ticker.upper().strip())

    # -- definitions --------------------------------------------------------------
    def list_definitions(self) -> list[AttributeDefinition]:
        return self._attributes.list_definitions()

    def update_definition(
        self,
        key: str,
        *,
        label: str | None = None,
        value_type: ValueType | None = None,
        scale_min: float | None = None,
        scale_max: float | None = None,
        allowed_values: list[str] | None = None,
        colors: dict[str, str] | None = None,
    ) -> AttributeDefinition:
        """Curate an existing key: rename its label, promote text -> scale,
        or attach an enum's allowed values/colors (e.g. `status`)."""
        canonical_key = canonicalize_attribute_key(key)
        existing = self._attributes.get_definition(canonical_key)
        if existing is None:
            raise NotFoundError(f"attribute {canonical_key!r} not defined")
        updated = AttributeDefinition(
            key=canonical_key,
            label=label if label is not None else existing.label,
            value_type=value_type if value_type is not None else existing.value_type,
            scale_min=scale_min if scale_min is not None else existing.scale_min,
            scale_max=scale_max if scale_max is not None else existing.scale_max,
            allowed_values=(
                allowed_values if allowed_values is not None else existing.allowed_values
            ),
            colors=colors if colors is not None else existing.colors,
        )
        stored = self._attributes.upsert_definition(updated)
        log.info("attribute.definition_updated", key=canonical_key)
        return stored

    # -- internals ------------------------------------------------------------------
    @staticmethod
    def _scale_bounds(
        value_type: ValueType, scale_min: float | None, scale_max: float | None
    ) -> tuple[float | None, float | None]:
        if value_type != "scale":
            return None, None
        if scale_min is not None and scale_max is not None:
            return scale_min, scale_max
        return _DEFAULT_SCALE

    @staticmethod
    def _validate_value(definition: AttributeDefinition, text: str) -> None:
        if definition.value_type == "number":
            try:
                float(text)
            except ValueError as exc:
                raise ValidationError(f"{definition.key!r} requires a numeric value") from exc
        elif definition.value_type == "scale":
            try:
                parsed = float(text)
            except ValueError as exc:
                raise ValidationError(f"{definition.key!r} requires a numeric value") from exc
            lo = definition.scale_min if definition.scale_min is not None else _DEFAULT_SCALE[0]
            hi = definition.scale_max if definition.scale_max is not None else _DEFAULT_SCALE[1]
            if not (lo <= parsed <= hi):
                raise ValidationError(f"{definition.key!r} must be between {lo:g} and {hi:g}")
        # "text": free-form on purpose — allowed_values is advisory, not
        # enforced (Phase 9: flexible now, curate/tighten later, no migration).
