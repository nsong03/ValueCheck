"""Phase 0: config is env-driven with local-first defaults."""

from __future__ import annotations

from pathlib import Path

import pytest

from equity.config import Settings


def test_defaults_boot_with_empty_env() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.app_name == "equity-research-platform"
    assert s.environment == "local"
    assert s.log_level == "INFO"
    assert s.edgar_identity is None
    assert isinstance(s.database_path, Path)


def test_env_prefix_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EQUITY_ENVIRONMENT", "prod")
    monkeypatch.setenv("EQUITY_LOG_JSON", "true")
    monkeypatch.setenv("EQUITY_EDGAR_IDENTITY", "Jane Doe jane@example.com")

    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert s.environment == "prod"
    assert s.log_json is True
    assert s.edgar_identity == "Jane Doe jane@example.com"
