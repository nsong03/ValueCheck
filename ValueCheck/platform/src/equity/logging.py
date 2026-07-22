"""Structured logging setup (structlog).

Call `configure_logging()` once at process start (the API app factory does this).
Get loggers elsewhere via `get_logger(__name__)`. The domain must NOT import this
module — logging is a side effect and the domain is pure (prime directive #2).
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import Processor

from equity.config import Settings, get_settings


def configure_logging(settings: Settings | None = None) -> None:
    """Configure stdlib logging + structlog from settings.

    Idempotent enough for repeated calls in tests; the last call wins.
    """
    settings = settings or get_settings()
    level = logging.getLevelName(settings.log_level.upper())
    if not isinstance(level, int):
        level = logging.INFO

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
