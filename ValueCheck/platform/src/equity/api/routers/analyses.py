"""Analyses router: the balcony — models/studies with explicit links to
companies, references, and other analyses."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from equity.api.deps import get_analyses
from equity.api.schemas.analysis import (
    AnalysisCompaniesOut,
    AnalysisIn,
    AnalysisLinksOut,
    AnalysisOut,
    AnalysisReferencesOut,
    AnalysisUpdate,
    LinkedAnalysisIn,
    ReferenceIdIn,
    TickerIn,
)
from equity.application.analysis_service import AnalysisService

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisOut, status_code=201)
def create_analysis(
    payload: AnalysisIn,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> AnalysisOut:
    return AnalysisOut.from_domain(
        analyses.create(kind=payload.kind, title=payload.title, summary=payload.summary)
    )


@router.get("", response_model=list[AnalysisOut])
def list_analyses(analyses: Annotated[AnalysisService, Depends(get_analyses)]) -> list[AnalysisOut]:
    return [AnalysisOut.from_domain(a) for a in analyses.list_all()]


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(
    analysis_id: int,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> AnalysisOut:
    return AnalysisOut.from_domain(analyses.get(analysis_id))


@router.patch("/{analysis_id}", response_model=AnalysisOut)
def update_analysis(
    analysis_id: int,
    payload: AnalysisUpdate,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> AnalysisOut:
    updated = analyses.update(
        analysis_id, kind=payload.kind, title=payload.title, summary=payload.summary
    )
    return AnalysisOut.from_domain(updated)


@router.delete("/{analysis_id}", status_code=204)
def delete_analysis(
    analysis_id: int,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> Response:
    analyses.delete(analysis_id)
    return Response(status_code=204)


# -- company constituents ------------------------------------------------------
@router.post("/{analysis_id}/companies", status_code=204)
def add_company(
    analysis_id: int,
    payload: TickerIn,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> Response:
    analyses.add_company(analysis_id, payload.ticker)
    return Response(status_code=204)


@router.delete("/{analysis_id}/companies/{ticker}", status_code=204)
def remove_company(
    analysis_id: int,
    ticker: str,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> Response:
    analyses.remove_company(analysis_id, ticker)
    return Response(status_code=204)


@router.get("/{analysis_id}/companies", response_model=AnalysisCompaniesOut)
def list_companies(
    analysis_id: int,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> AnalysisCompaniesOut:
    return AnalysisCompaniesOut(tickers=analyses.companies(analysis_id))


@router.get("/for-company/{ticker}", response_model=list[AnalysisOut])
def analyses_for_company(
    ticker: str,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> list[AnalysisOut]:
    """What models have I built that touch this stock?"""
    return [AnalysisOut.from_domain(a) for a in analyses.analyses_for_company(ticker)]


# -- reference constituents -----------------------------------------------------
@router.post("/{analysis_id}/references", status_code=204)
def add_reference(
    analysis_id: int,
    payload: ReferenceIdIn,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> Response:
    analyses.add_reference(analysis_id, payload.reference_id)
    return Response(status_code=204)


@router.delete("/{analysis_id}/references/{reference_id}", status_code=204)
def remove_reference(
    analysis_id: int,
    reference_id: int,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> Response:
    analyses.remove_reference(analysis_id, reference_id)
    return Response(status_code=204)


@router.get("/{analysis_id}/references", response_model=AnalysisReferencesOut)
def list_references(
    analysis_id: int,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> AnalysisReferencesOut:
    return AnalysisReferencesOut(reference_ids=analyses.references(analysis_id))


@router.get("/for-reference/{reference_id}", response_model=list[AnalysisOut])
def analyses_for_reference(
    reference_id: int,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> list[AnalysisOut]:
    """What models have I built that cite this book/article/PDF?"""
    return [AnalysisOut.from_domain(a) for a in analyses.analyses_for_reference(reference_id)]


# -- analysis <-> analysis links --------------------------------------------------
@router.post("/{analysis_id}/links", status_code=204)
def add_link(
    analysis_id: int,
    payload: LinkedAnalysisIn,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> Response:
    analyses.add_link(analysis_id, payload.linked_analysis_id)
    return Response(status_code=204)


@router.delete("/{analysis_id}/links/{linked_analysis_id}", status_code=204)
def remove_link(
    analysis_id: int,
    linked_analysis_id: int,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> Response:
    analyses.remove_link(analysis_id, linked_analysis_id)
    return Response(status_code=204)


@router.get("/{analysis_id}/links", response_model=AnalysisLinksOut)
def list_links(
    analysis_id: int,
    analyses: Annotated[AnalysisService, Depends(get_analyses)],
) -> AnalysisLinksOut:
    return AnalysisLinksOut(analysis_ids=analyses.links(analysis_id))
