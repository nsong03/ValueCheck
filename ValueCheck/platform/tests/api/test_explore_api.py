"""Search + graph endpoints (Phase 8 acceptance via the HTTP contract)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def seed_research(client: TestClient) -> None:
    # companies enter through the normal cache-first path (fake filings)
    client.get("/companies/AAPL")
    client.get("/companies/TSM")
    for payload in (
        {"ticker": "AAPL", "title": "Ecosystem", "body": "Sticky services.", "tags": ["moat"]},
        {
            "ticker": "TSM",
            "title": "Fab risk",
            "body": "Chip shortage exposure.",
            "tags": ["semis"],
        },
        {"ticker": "TSM", "title": "Pricing", "body": "Wafer pricing power.", "tags": ["semis"]},
    ):
        assert client.post("/notes", json=payload).status_code == 201


class TestSearchEndpoint:
    def test_event_query_returns_impacted_companies(self, client: TestClient) -> None:
        seed_research(client)
        resp = client.get("/search", params={"q": "chip shortage"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "chip shortage"
        assert body["impacted_tickers"] == ["TSM"]
        assert body["hits"][0]["title"] == "Fab risk"
        assert "[" in body["hits"][0]["snippet"]  # highlighted match

    def test_missing_query_is_validation_error(self, client: TestClient) -> None:
        resp = client.get("/search")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    def test_no_results(self, client: TestClient) -> None:
        resp = client.get("/search", params={"q": "unindexed topic"})
        assert resp.status_code == 200
        assert resp.json()["impacted_tickers"] == []


class TestGraphEndpoint:
    def test_full_graph(self, client: TestClient) -> None:
        seed_research(client)
        resp = client.get("/graph")
        assert resp.status_code == 200
        body = resp.json()
        node_ids = {n["id"] for n in body["nodes"]}
        assert {"AAPL", "TSM", "tag:moat", "tag:semis"} <= node_ids
        weights = {(e["source"], e["target"]): e["weight"] for e in body["edges"]}
        assert weights[("TSM", "tag:semis")] == 2

    def test_filtered_by_impacted_set(self, client: TestClient) -> None:
        """search -> impacted tickers -> filtered subgraph (the Phase 8 flow)."""
        seed_research(client)
        impacted = client.get("/search", params={"q": "chip shortage"}).json()["impacted_tickers"]
        resp = client.get("/graph", params={"tickers": impacted})
        assert resp.status_code == 200
        node_ids = {n["id"] for n in resp.json()["nodes"]}
        assert node_ids == {"TSM", "tag:semis"}

    def test_filtered_by_sector(self, client: TestClient) -> None:
        seed_research(client)
        resp = client.get("/graph", params={"sector": "Technology"})
        assert resp.status_code == 200
        companies = {n["id"] for n in resp.json()["nodes"] if n["kind"] == "company"}
        assert companies == {"AAPL", "TSM"}  # fake filings give every company this sector
