"""FastAPI application factory.

Phase 0: an empty-but-typed app exposing `/health`. Business routers and DI are
wired in later phases (§ BUILD_SPEC Phase 5). Kept thin by design — no business
logic lives here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from equity import __version__
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


def _error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log.info("app.startup", app=settings.app_name, environment=settings.environment)
        yield
        log.info("app.shutdown", app=settings.app_name)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )

    @app.exception_handler(EquityError)
    async def _handle_equity_error(_: Request, exc: EquityError) -> JSONResponse:
        log.warning("request.error", code=exc.code.value, message=exc.message)
        return _error_response(exc.code.value, exc.message, int(exc.http_status))

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            app=settings.app_name,
            version=__version__,
            environment=settings.environment,
        )

    return app


# ASGI entrypoint for `uvicorn equity.api.main:app`.
app = create_app()
