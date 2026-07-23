"""Attributes router: typed, namespaced company facts with full history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from equity.api.deps import get_attributes
from equity.api.schemas.attributes import (
    AttributeDefinitionOut,
    AttributeDefinitionPatch,
    AttributeHistoryOut,
    AttributeValueIn,
    AttributeValueOut,
)
from equity.application.attribute_service import AttributeService, canonicalize_attribute_key

router = APIRouter(tags=["attributes"])


@router.get("/attributes/definitions", response_model=list[AttributeDefinitionOut])
def list_definitions(
    attributes: Annotated[AttributeService, Depends(get_attributes)],
) -> list[AttributeDefinitionOut]:
    """Every known attribute key, for the Attributes panel + screener columns."""
    return [AttributeDefinitionOut.from_domain(d) for d in attributes.list_definitions()]


@router.patch("/attributes/definitions/{key}", response_model=AttributeDefinitionOut)
def update_definition(
    key: str,
    payload: AttributeDefinitionPatch,
    attributes: Annotated[AttributeService, Depends(get_attributes)],
) -> AttributeDefinitionOut:
    """Curate a key: rename its label, promote text -> scale, or attach an
    enum's allowed values/colors (e.g. `status`)."""
    updated = attributes.update_definition(key, **payload.model_dump(exclude_unset=True))
    return AttributeDefinitionOut.from_domain(updated)


@router.post("/companies/{ticker}/attributes", response_model=AttributeValueOut, status_code=201)
def set_attribute(
    ticker: str,
    payload: AttributeValueIn,
    attributes: Annotated[AttributeService, Depends(get_attributes)],
) -> AttributeValueOut:
    """Record one attribute value, from a note save or a direct grid edit."""
    stored = attributes.set_value(
        ticker,
        payload.key,
        payload.value,
        source=payload.source,
        note_id=payload.note_id,
        reason=payload.reason,
        value_type=payload.value_type,
        label=payload.label,
        scale_min=payload.scale_min,
        scale_max=payload.scale_max,
    )
    return AttributeValueOut.from_domain(stored)


@router.get("/companies/{ticker}/attributes", response_model=dict[str, AttributeValueOut])
def current_attributes(
    ticker: str,
    attributes: Annotated[AttributeService, Depends(get_attributes)],
) -> dict[str, AttributeValueOut]:
    """Current (latest) value per key for one company."""
    return {
        key: AttributeValueOut.from_domain(v)
        for key, v in attributes.current_values(ticker).items()
    }


@router.get("/companies/{ticker}/attributes/{key}/history", response_model=AttributeHistoryOut)
def attribute_history(
    ticker: str,
    key: str,
    attributes: Annotated[AttributeService, Depends(get_attributes)],
) -> AttributeHistoryOut:
    """The full timeline for one (ticker, key) dimension, newest first —
    e.g. how a moat score evolved as the thesis was revisited."""
    values = attributes.history(ticker, key)
    return AttributeHistoryOut(
        ticker=ticker.upper().strip(),
        key=canonicalize_attribute_key(key),
        values=[AttributeValueOut.from_domain(v) for v in values],
    )
