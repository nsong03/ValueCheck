"""Application settings — env-driven, no hardcoded paths/URLs/keys.

CLAUDE.md prime directive #6: everything configurable flows through here
(pydantic-settings). Read once at process start via `get_settings()`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, populated from the environment / `.env`.

    All fields have safe local-first defaults so the app boots with an empty
    environment; anything host- or secret-specific must be supplied via env.
    """

    model_config = SettingsConfigDict(
        env_prefix="EQUITY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- app -----------------------------------------------------------------
    app_name: str = "equity-research-platform"
    environment: str = Field(
        default="local",
        description="Deployment environment name (local, ci, prod, ...).",
    )
    debug: bool = False

    # -- logging -------------------------------------------------------------
    log_level: str = Field(default="INFO", description="Root log level.")
    log_json: bool = Field(
        default=False,
        description="Emit JSON logs (True) vs. human-readable console logs (False).",
    )

    # -- persistence ---------------------------------------------------------
    # SQLite path; repositories sit behind ports so this is a later swap point.
    database_path: Path = Field(
        default=Path("equity.db"),
        description="Filesystem path to the SQLite database.",
    )

    # -- SEC EDGAR -----------------------------------------------------------
    # SEC fair-access requires an identifying User-Agent. Never hardcode an
    # email (CLAUDE.md); it is supplied via EQUITY_EDGAR_IDENTITY.
    edgar_identity: str | None = Field(
        default=None,
        description='SEC EDGAR identity header, e.g. "Jane Doe jane@example.com".',
    )
    edgar_rate_limit_per_sec: float = Field(
        default=5.0,
        description="Max requests/second to SEC EDGAR (fair-access throttle).",
    )

    # -- market data ---------------------------------------------------------
    request_timeout_seconds: float = Field(
        default=15.0,
        description="Default timeout for outbound market/filings HTTP calls.",
    )

    # -- knowledge library (Phase 9b) -----------------------------------------
    reference_library_path: Path | None = Field(
        default=None,
        description=(
            "Root folder to scan for PDFs (recursively; organized into "
            "collections by subfolder). Unset = scanning disabled."
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton (cached)."""
    return Settings()
