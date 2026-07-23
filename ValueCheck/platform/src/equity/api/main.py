"""FastAPI application factory.

Thin by design: routing, DI wiring, and error mapping only — business logic
lives in application services, math in the domain. All errors leave in one
envelope: {"error": {"code": ..., "message": ..., "details": [...]?}}.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from equity import __version__
from equity.api.routers import (
    analyses,
    attributes,
    companies,
    graph,
    notes,
    references,
    screener,
    search,
    tags,
    valuations,
)
from equity.application.container import Container, build_container
from equity.config import Settings, get_settings
from equity.errors import EquityError
from equity.logging import configure_logging, get_logger

log = get_logger(__name__)


class HealthResponse(BaseModel):
    """Liveness payload."""

    status: str = "ok"
    app: str
    version: str
    environment: str


def _error_response(
    code: str,
    message: str,
    status_code: int,
    details: object = None,
) -> JSONResponse:
    body: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    """Build and configure the FastAPI application.

    Tests inject a pre-built `container` (fakes, temp db); production leaves
    it None and the lifespan builds the real one (migrating the db) at startup.
    """
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app_: FastAPI) -> AsyncIterator[None]:
        if app_.state.container is None:
            app_.state.container = build_container(settings)
        built: Container = app_.state.container
        try:
            scanned = built.reference_service.scan()
            if scanned:
                log.info("references.startup_scan", created=len(scanned))
        except Exception:
            log.warning("references.startup_scan_failed", exc_info=True)
        log.info("app.startup", app=settings.app_name, environment=settings.environment)
        yield
        log.info("app.shutdown", app=settings.app_name)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    app.state.container = container

    @app.exception_handler(EquityError)
    async def _handle_equity_error(_: Request, exc: EquityError) -> JSONResponse:
        log.warning("request.error", code=exc.code.value, message=exc.message)
        return _error_response(exc.code.value, exc.message, int(exc.http_status))

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            "validation_error",
            "request validation failed",
            422,
            details=jsonable_encoder(exc.errors()),
        )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            app=settings.app_name,
            version=__version__,
            environment=settings.environment,
        )

    app.include_router(companies.router)
    app.include_router(valuations.router)
    app.include_router(notes.router)
    app.include_router(tags.router)
    app.include_router(search.router)
    app.include_router(graph.router)
    app.include_router(attributes.router)
    app.include_router(screener.router)
    app.include_router(references.router)
    app.include_router(analyses.router)

    return app


# ASGI entrypoint for `uvicorn equity.api.main:app`.
app = create_app()
