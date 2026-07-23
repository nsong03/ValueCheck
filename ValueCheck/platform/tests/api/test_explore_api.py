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

    def test_reference_note_links_via_shared_tag(self, client: TestClient) -> None:
        """Phase 9b: a book/PDF is a third node kind, connected to companies
        through a tag both carry — no direct company<->reference edge needed."""
        seed_research(client)
        ref = client.post(
            "/references",
            json={"kind": "book", "title": "Fabless Semiconductors", "location": "https://x/fab"},
        ).json()
        client.post(
            "/notes",
            json={
                "reference_id": ref["id"],
                "title": "Ch. 4",
                "body": "",
                "tags": ["semis"],
            },
        )

        resp = client.get("/graph")
        assert resp.status_code == 200
        body = resp.json()
        ref_id = f"reference:{ref['id']}"
        refs = {n["id"]: n for n in body["nodes"] if n["kind"] == "reference"}
        assert refs[ref_id]["label"] == "Fabless Semiconductors"

        edges = {(e["source"], e["target"]) for e in body["edges"]}
        assert (ref_id, "tag:semis") in edges
        assert ("TSM", "tag:semis") in edges

    def test_collection_filter(self, client: TestClient) -> None:
        client.post(
            "/references",
            json={
                "kind": "pdf",
                "title": "In collection",
                "location": "C:/a.pdf",
                "collection": "Valuation",
            },
        )
        client.post(
            "/references",
            json={"kind": "pdf", "title": "Not in collection", "location": "C:/b.pdf"},
        )
        resp = client.get("/graph", params={"collection": "Valuation"})
        assert resp.status_code == 200
        labels = {n["label"] for n in resp.json()["nodes"] if n["kind"] == "reference"}
        assert labels == {"In collection"}

    def test_tickers_filter_drops_references(self, client: TestClient) -> None:
        seed_research(client)
        client.post(
            "/references", json={"kind": "pdf", "title": "Unrelated PDF", "location": "C:/c.pdf"}
        )
        resp = client.get("/graph", params={"tickers": ["AAPL"]})
        assert resp.status_code == 200
        assert not any(n["kind"] == "reference" for n in resp.json()["nodes"])

    def test_analysis_node_with_explicit_company_link(self, client: TestClient) -> None:
        """Phase 9c: an analysis's link to a company is a `kind: "link"` edge
        (deliberate), distinct from the `kind: "tag"` edges above (incidental)."""
        seed_research(client)
        analysis = client.post(
            "/analyses", json={"kind": "correlation-study", "title": "Semis Study"}
        ).json()
        client.post(f"/analyses/{analysis['id']}/companies", json={"ticker": "TSM"})

        resp = client.get("/graph")
        assert resp.status_code == 200
        body = resp.json()
        an_id = f"analysis:{analysis['id']}"
        assert any(n["id"] == an_id and n["kind"] == "analysis" for n in body["nodes"])

        link_edges = {(e["source"], e["target"]) for e in body["edges"] if e["kind"] == "link"}
        assert (an_id, "TSM") in link_edges or ("TSM", an_id) in link_edges
