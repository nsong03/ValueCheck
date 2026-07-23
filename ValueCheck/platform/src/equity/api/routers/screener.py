"""Screener router: spreadsheet-style view over every company, its latest
valuation, and current research attributes (Phase 9)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from equity.api.deps import get_screener
from equity.api.schemas.attributes import AttributeDefinitionOut
from equity.api.schemas.screener import ScreenerColumnsOut, ScreenerOut, ScreenerRowOut
from equity.application.screener_service import ScreenerService

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("/rows", response_model=ScreenerOut)
def screener_rows(screener: Annotated[ScreenerService, Depends(get_screener)]) -> ScreenerOut:
    """One row per tracked company: financials, latest valuation, tags, and
    current research attributes."""
    return ScreenerOut(rows=[ScreenerRowOut.from_domain(r) for r in screener.build_rows()])


@router.get("/columns", response_model=ScreenerColumnsOut)
def screener_columns(
    screener: Annotated[ScreenerService, Depends(get_screener)],
) -> ScreenerColumnsOut:
    """Discovered attribute keys + types, so the frontend can build columns
    for custom dimensions (region, quality scores, status) dynamically."""
    return ScreenerColumnsOut(
        columns=[AttributeDefinitionOut.from_domain(d) for d in screener.columns()]
    )
