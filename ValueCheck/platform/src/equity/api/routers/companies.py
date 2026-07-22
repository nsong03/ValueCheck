"""Companies router: on-demand company data + the valuation endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query

from equity.api.deps import get_companies, get_ingestion, get_valuation
from equity.api.schemas.company import CompanyDetail, CompanyListOut
from equity.api.schemas.valuation import (
    AssumptionsIn,
    ValuationRecordSummary,
    ValuationResponse,
)
from equity.application.ingestion_service import IngestionService
from equity.application.valuation_service import ValuationService
from equity.ports.repository import CompanyRepo

router = APIRouter(prefix="/companies", tags=["companies"])

Refresh = Annotated[bool, Query(description="Bypass the cache and refetch filings + market data.")]


@router.get("", response_model=CompanyListOut)
def list_companies(repo: Annotated[CompanyRepo, Depends(get_companies)]) -> CompanyListOut:
    return CompanyListOut(tickers=repo.list_tickers())


@router.get("/{ticker}", response_model=CompanyDetail)
def get_company(
    ticker: str,
    ingestion: Annotated[IngestionService, Depends(get_ingestion)],
    refresh: Refresh = False,
) -> CompanyDetail:
    """Normalized financials, cache-first (fetches live on first sight)."""
    fin = ingestion.get_company(ticker, refresh=refresh)
    return CompanyDetail.from_domain(fin)


@router.post("/{ticker}/valuation", response_model=ValuationResponse)
def run_valuation(
    ticker: str,
    valuation: Annotated[ValuationService, Depends(get_valuation)],
    assumptions: Annotated[AssumptionsIn | None, Body()] = None,
    refresh: Refresh = False,
) -> ValuationResponse:
    """Run a DCF. Omitted assumption fields seed from the company's history;
    the response carries the result, sensitivity grid, and source links."""
    overrides = assumptions.overrides() if assumptions is not None else {}
    outcome = valuation.value(ticker, overrides=overrides, refresh=refresh)
    return ValuationResponse.from_outcome(outcome)


@router.get("/{ticker}/valuations", response_model=list[ValuationRecordSummary])
def valuation_history(
    ticker: str,
    valuation: Annotated[ValuationService, Depends(get_valuation)],
) -> list[ValuationRecordSummary]:
    """Stored runs for this company, newest first."""
    return [ValuationRecordSummary.from_record(r) for r in valuation.history(ticker)]
