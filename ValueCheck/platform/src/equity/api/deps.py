"""FastAPI dependencies: hand routers their services from the container.

The container is built once (lifespan, or injected by tests) and stashed on
`app.state`; routers never construct adapters themselves.
"""

from __future__ import annotations

from fastapi import Request

from equity.application.analysis_service import AnalysisService
from equity.application.attribute_service import AttributeService
from equity.application.container import Container
from equity.application.graph_service import GraphService
from equity.application.ingestion_service import IngestionService
from equity.application.reference_service import ReferenceService
from equity.application.research_service import ResearchService
from equity.application.screener_service import ScreenerService
from equity.application.search_service import SearchService
from equity.application.valuation_service import ValuationService
from equity.ports.repository import CompanyRepo


def get_container(request: Request) -> Container:
    container: Container | None = getattr(request.app.state, "container", None)
    if container is None:  # pragma: no cover — programming error, not a request path
        raise RuntimeError("application container not initialized")
    return container


def get_ingestion(request: Request) -> IngestionService:
    return get_container(request).ingestion


def get_valuation(request: Request) -> ValuationService:
    return get_container(request).valuation


def get_companies(request: Request) -> CompanyRepo:
    return get_container(request).companies


def get_research(request: Request) -> ResearchService:
    return get_container(request).research


def get_search(request: Request) -> SearchService:
    return get_container(request).search


def get_graph(request: Request) -> GraphService:
    return get_container(request).graph


def get_attributes(request: Request) -> AttributeService:
    return get_container(request).attribute_service


def get_screener(request: Request) -> ScreenerService:
    return get_container(request).screener


def get_references(request: Request) -> ReferenceService:
    return get_container(request).reference_service


def get_analyses(request: Request) -> AnalysisService:
    return get_container(request).analysis_service
