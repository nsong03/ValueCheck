"""Companies endpoints: success, validation-error, and upstream-error paths."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from equity.errors import ErrorCode, UpstreamError

from .conftest import FakeFilings

GOLDEN_FAIR_VALUE = 98.31624329048412  # Phase 1 golden, seed engine
GOLDEN_FAIR_VALUE_B = 102.91513865323917  # ebit_margin=0.29, g=0.025 override


class TestRunValuation:
    def test_empty_body_seeds_from_history(self, client: TestClient) -> None:
        resp = client.post("/companies/DEMO/valuation", json={})
        assert resp.status_code == 200
        body = resp.json()

        assert body["ticker"] == "DEMO"
        assert body["valuation_id"] >= 1
        assert body["fair_value_per_share"] == pytest.approx(GOLDEN_FAIR_VALUE, rel=1e-9)
        assert body["warnings"] == []
        # resolved assumptions echo what was actually used
        assert body["assumptions"]["ebit_margin"] == pytest.approx(0.2772)
        assert body["assumptions"]["beta"] == pytest.approx(1.28)
        # projection: 5 years, full FCFF build
        assert len(body["projection"]) == 5
        assert set(body["projection"][0]) == {
            "year",
            "revenue",
            "growth",
            "ebit",
            "nopat",
            "da",
            "capex",
            "d_nwc",
            "fcff",
            "discount",
            "pv_fcff",
        }
        # sensitivity grid 5x5 with labels
        sens = body["sensitivity"]
        assert len(sens["wacc_labels"]) == 5
        assert len(sens["growth_labels"]) == 5
        assert len(sens["grid"]) == 5 and len(sens["grid"][0]) == 5
        # sources: 5 filings + 1 market
        assert len(body["sources"]) == 6

    def test_partial_overrides(self, client: TestClient) -> None:
        resp = client.post(
            "/companies/DEMO/valuation",
            json={"ebit_margin": 0.29, "terminal_growth": 0.025},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["fair_value_per_share"] == pytest.approx(GOLDEN_FAIR_VALUE_B, rel=1e-9)
        assert body["assumptions"]["ebit_margin"] == 0.29
        # untouched levers still seeded from history
        assert body["assumptions"]["tax_rate"] == pytest.approx(0.149)

    def test_no_body_at_all(self, client: TestClient) -> None:
        resp = client.post("/companies/DEMO/valuation")
        assert resp.status_code == 200

    def test_warnings_surface(self, client: TestClient) -> None:
        resp = client.post("/companies/DEMO/valuation", json={"terminal_growth": 0.09})
        assert resp.status_code == 200
        assert any("sensitive" in w for w in resp.json()["warnings"])


class TestValidationErrors:
    def test_out_of_bounds_field(self, client: TestClient) -> None:
        resp = client.post("/companies/DEMO/valuation", json={"horizon": 0})
        assert resp.status_code == 422
        err = resp.json()["error"]
        assert err["code"] == "validation_error"
        assert any("horizon" in str(d.get("loc")) for d in err["details"])

    def test_wrong_type(self, client: TestClient) -> None:
        resp = client.post("/companies/DEMO/valuation", json={"ebit_margin": "lots"})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    def test_unknown_field_rejected_shape_kept(self, client: TestClient) -> None:
        # unknown fields are ignored by default (additive API evolution),
        # but bounds still apply to known ones in the same payload
        resp = client.post(
            "/companies/DEMO/valuation",
            json={"nonsense": 1, "tax_rate": 3.0},
        )
        assert resp.status_code == 422


class TestUpstreamErrors:
    def test_filings_outage_maps_to_502_envelope(
        self, client: TestClient, fake_filings: FakeFilings
    ) -> None:
        fake_filings.fail_with = UpstreamError("sec down", code=ErrorCode.FILINGS_UNAVAILABLE)
        resp = client.post("/companies/NEWCO/valuation", json={})
        assert resp.status_code == 502
        err = resp.json()["error"]
        assert err["code"] == "filings_unavailable"
        assert "sec down" in err["message"]

    def test_cached_company_survives_outage(
        self, client: TestClient, fake_filings: FakeFilings
    ) -> None:
        assert client.post("/companies/DEMO/valuation", json={}).status_code == 200
        fake_filings.fail_with = UpstreamError("sec down", code=ErrorCode.FILINGS_UNAVAILABLE)
        resp = client.post("/companies/DEMO/valuation", json={})
        assert resp.status_code == 200  # cache-first


class TestCompanyEndpoints:
    def test_get_company_detail(self, client: TestClient) -> None:
        resp = client.get("/companies/DEMO")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "DEMO"
        assert body["name"] == "Demo Hardware Inc."
        assert body["price"] == 195.0  # market-enriched
        assert body["market_cap"] == pytest.approx(3_032_250.0)
        assert body["revenue_cagr"] == pytest.approx(0.10170287389225408)
        rows = body["historicals"]
        assert [r["fiscal_year"] for r in rows] == [2019, 2020, 2021, 2022, 2023]
        assert rows[-1]["revenue"] == pytest.approx(383285.0)
        assert len(body["sources"]) == 6

    def test_get_company_uses_cache(self, client: TestClient, fake_filings: FakeFilings) -> None:
        client.get("/companies/DEMO")
        client.get("/companies/DEMO")
        assert fake_filings.calls == 1

    def test_list_companies(self, client: TestClient) -> None:
        assert client.get("/companies").json() == {"tickers": []}
        client.get("/companies/DEMO")
        assert client.get("/companies").json() == {"tickers": ["DEMO"]}

    def test_history_endpoint_newest_first(self, client: TestClient) -> None:
        first = client.post("/companies/DEMO/valuation", json={}).json()["valuation_id"]
        second = client.post("/companies/DEMO/valuation", json={}).json()["valuation_id"]
        resp = client.get("/companies/DEMO/valuations")
        assert resp.status_code == 200
        assert [r["id"] for r in resp.json()] == [second, first]
