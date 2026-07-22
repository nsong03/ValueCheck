"""Typed exceptions with stable error codes.

Stable `ErrorCode` values are part of the app's contract: they surface in API
error responses and logs, so treat them as append-only. This module is pure
(no I/O) and may be imported from any layer, including the domain, since it
declares only types — it imports nothing internal outward.
"""

from __future__ import annotations

from enum import StrEnum
from http import HTTPStatus


class ErrorCode(StrEnum):
    """Stable, append-only error codes surfaced to clients and logs."""

    # generic
    INTERNAL = "internal_error"
    VALIDATION = "validation_error"
    NOT_FOUND = "not_found"

    # domain
    INVALID_ASSUMPTIONS = "invalid_assumptions"
    INSUFFICIENT_HISTORY = "insufficient_history"

    # adapters / external data
    FILINGS_UNAVAILABLE = "filings_unavailable"
    MARKET_DATA_UNAVAILABLE = "market_data_unavailable"
    UPSTREAM_TIMEOUT = "upstream_timeout"

    # persistence
    PERSISTENCE_ERROR = "persistence_error"
    CONFLICT = "conflict"


class EquityError(Exception):
    """Base class for all application errors.

    Carries a stable `code` and a default HTTP status so the API layer can map
    any domain/adapter failure to a response without knowing concrete types.
    """

    code: ErrorCode = ErrorCode.INTERNAL
    http_status: HTTPStatus = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message: str, *, code: ErrorCode | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code

    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"


class ValidationError(EquityError):
    code = ErrorCode.VALIDATION
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY


class NotFoundError(EquityError):
    code = ErrorCode.NOT_FOUND
    http_status = HTTPStatus.NOT_FOUND


class DomainError(EquityError):
    """Base for pure-domain rule violations."""

    http_status = HTTPStatus.UNPROCESSABLE_ENTITY


class UpstreamError(EquityError):
    """Base for failures talking to an external data source (adapters)."""

    http_status = HTTPStatus.BAD_GATEWAY


class PersistenceError(EquityError):
    code = ErrorCode.PERSISTENCE_ERROR
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR
