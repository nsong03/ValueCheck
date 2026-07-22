"""Shared test fixtures. Domain/unit tests must run with no network."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from equity.config import Settings, get_settings


@pytest.fixture
def settings() -> Settings:
    """A fresh, default Settings instance for tests."""
    return Settings()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """Ensure the cached settings singleton doesn't leak across tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
