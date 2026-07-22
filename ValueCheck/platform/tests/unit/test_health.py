"""Phase 0 smoke: the app boots and /health responds."""

from __future__ import annotations

from fastapi.testclient import TestClient

from equity.api.main import create_app
from equity.config import Settings


def test_health_ok() -> None:
    app = create_app(Settings(app_name="test-app", environment="ci"))
    client = TestClient(app)

    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "test-app"
    assert body["environment"] == "ci"
    assert body["version"]


def test_openapi_schema_available() -> None:
    app = create_app(Settings())
    client = TestClient(app)

    resp = client.get("/openapi.json")

    assert resp.status_code == 200
    assert "/health" in resp.json()["paths"]
