"""Valuations router: retrieve stored runs by id."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from equity.api.deps import get_valuation
from equity.api.schemas.valuation import ValuationRecordDetail
from equity.application.valuation_service import ValuationService
from equity.errors import NotFoundError

router = APIRouter(prefix="/valuations", tags=["valuations"])


@router.get("/{valuation_id}", response_model=ValuationRecordDetail)
def get_valuation_record(
    valuation_id: int,
    valuation: Annotated[ValuationService, Depends(get_valuation)],
) -> ValuationRecordDetail:
    record = valuation.get(valuation_id)
    if record is None:
        raise NotFoundError(f"valuation {valuation_id} not found")
    return ValuationRecordDetail.from_record(record)
