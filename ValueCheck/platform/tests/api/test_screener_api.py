"""Screener endpoints: rows join financials, valuation, tags, and attributes;
columns expose the discovered attribute definitions."""

from __future__ import annotations

from fastapi.testclient import TestClient


def load_company(client: TestClient, ticker: str = "DEMO") -> None:
    resp = client.get(f"/companies/{ticker}")
    assert resp.status_code == 200, resp.text


class TestScreenerRows:
    def test_empty_when_no_companies_tracked(self, client: TestClient) -> None:
        assert client.get("/screener/rows").json() == {"rows": []}

    def test_row_reflects_financials_tags_and_attributes(self, client: TestClient) -> None:
        load_company(client)
        client.post("/notes", json={"ticker": "DEMO", "title": "t", "body": "", "tags": ["moat"]})
        client.post(
            "/companies/DEMO/attributes",
            json={"key": "region", "value": "us", "source": "note"},
        )

        rows = client.get("/screener/rows").json()["rows"]
        assert len(rows) == 1
        row = rows[0]
        assert row["ticker"] == "DEMO"
        assert row["tags"] == ["moat"]
        assert row["note_count"] == 1
        assert row["attributes"]["region"]["value"] == "us"

    def test_row_reflects_a_run_valuation(self, client: TestClient) -> None:
        load_company(client)
        client.post("/companies/DEMO/valuation", json={})
        row = client.get("/screener/rows").json()["rows"][0]
        assert row["latest_valuation"] is not None
        assert row["latest_valuation"]["fair_value_per_share"] is not None


class TestScreenerColumns:
    def test_columns_reflect_discovered_attribute_keys(self, client: TestClient) -> None:
        load_company(client)
        client.post(
            "/companies/DEMO/attributes",
            json={
                "key": "quality.moat",
                "value": "4",
                "source": "note",
                "value_type": "scale",
            },
        )
        columns = client.get("/screener/columns").json()["columns"]
        assert [c["key"] for c in columns] == ["quality.moat"]
        assert columns[0]["value_type"] == "scale"
