"""Valuations-by-id endpoint + JSON edge cases (NaN -> null)."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from equity.domain.models import MarketSnapshot

from .conftest import FakeMarket


class TestGetValuation:
    def test_round_trip_by_id(self, client: TestClient) -> None:
        created = client.post("/companies/DEMO/valuation", json={}).json()
        resp = client.get(f"/valuations/{created['valuation_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == created["valuation_id"]
        assert body["fair_value_per_share"] == created["fair_value_per_share"]
        assert body["assumptions"] == created["assumptions"]
        assert body["projection"] == created["projection"]

    def test_missing_id_is_404_envelope(self, client: TestClient) -> None:
        resp = client.get("/valuations/999999")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    def test_non_int_id_is_validation_error(self, client: TestClient) -> None:
        resp = client.get("/valuations/abc")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"


class TestNanBecomesNull:
    def test_missing_shares_and_price_yield_nulls(
        self, client: TestClient, fake_market: FakeMarket
    ) -> None:
        # market data with no price/shares -> per-share + upside are undefined
        fake_market.override = MarketSnapshot(
            price=0.0,
            shares_out=0.0,
            total_debt=111088.0,
            cash=61555.0,
            beta=1.28,
            provider="mock",
            as_of=dt.date.today().isoformat(),
            source_url="about:mock",
        )
        resp = client.post("/companies/DEMO/valuation", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["fair_value_per_share"] is None  # NaN -> null, valid JSON
        assert body["upside"] is None
        assert body["enterprise_value"] == pytest.approx(1578350.5831670281, rel=1e-9)


class TestOpenAPI:
    def test_schema_exports_cleanly(self, client: TestClient) -> None:
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert "/companies/{ticker}/valuation" in spec["paths"]
        assert "/valuations/{valuation_id}" in spec["paths"]
        # response schema carries the §5 contract fields
        names = set(spec["components"]["schemas"])
        assert {"ValuationResponse", "AssumptionsIn", "SensitivityOut", "CompanyDetail"} <= names
