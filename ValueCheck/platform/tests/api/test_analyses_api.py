"""Analyses endpoints: the balcony CRUD, plus explicit links to companies,
references, and other analyses (Phase 9c)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def make_analysis(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"kind": "portfolio", "title": "Core Holdings", "summary": ""}
    payload.update(overrides)
    resp = client.post("/analyses", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_reference(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"kind": "pdf", "title": "A Paper", "location": "https://x/paper"}
    payload.update(overrides)
    resp = client.post("/references", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestAnalysesCrud:
    def test_create_and_get(self, client: TestClient) -> None:
        created = make_analysis(client)
        got = client.get(f"/analyses/{created['id']}")
        assert got.status_code == 200
        assert got.json() == created

    def test_list_all(self, client: TestClient) -> None:
        make_analysis(client, title="A")
        make_analysis(client, title="B")
        listed = client.get("/analyses").json()
        assert {a["title"] for a in listed} == {"A", "B"}

    def test_update(self, client: TestClient) -> None:
        created = make_analysis(client)
        resp = client.patch(f"/analyses/{created['id']}", json={"title": "Revised"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Revised"
        assert resp.json()["kind"] == created["kind"]

    def test_update_missing_returns_404(self, client: TestClient) -> None:
        assert client.patch("/analyses/999", json={"title": "x"}).status_code == 404

    def test_delete(self, client: TestClient) -> None:
        created = make_analysis(client)
        assert client.delete(f"/analyses/{created['id']}").status_code == 204
        assert client.get(f"/analyses/{created['id']}").status_code == 404

    def test_validation_envelope(self, client: TestClient) -> None:
        resp = client.post("/analyses", json={"kind": "", "title": ""})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"


class TestCompanyConstituents:
    def test_add_list_remove(self, client: TestClient) -> None:
        created = make_analysis(client)
        aid = created["id"]
        assert client.post(f"/analyses/{aid}/companies", json={"ticker": "aapl"}).status_code == 204
        assert client.get(f"/analyses/{aid}/companies").json() == {"tickers": ["AAPL"]}
        assert client.delete(f"/analyses/{aid}/companies/AAPL").status_code == 204
        assert client.get(f"/analyses/{aid}/companies").json() == {"tickers": []}

    def test_reverse_lookup(self, client: TestClient) -> None:
        a = make_analysis(client, title="A")
        b = make_analysis(client, title="B")
        client.post(f"/analyses/{a['id']}/companies", json={"ticker": "AAPL"})
        client.post(f"/analyses/{b['id']}/companies", json={"ticker": "AAPL"})

        touching = client.get("/analyses/for-company/AAPL").json()
        assert {x["id"] for x in touching} == {a["id"], b["id"]}


class TestReferenceConstituents:
    def test_add_list_remove(self, client: TestClient) -> None:
        created = make_analysis(client)
        ref = make_reference(client)
        aid, rid = created["id"], ref["id"]

        resp = client.post(f"/analyses/{aid}/references", json={"reference_id": rid})
        assert resp.status_code == 204
        assert client.get(f"/analyses/{aid}/references").json() == {"reference_ids": [rid]}
        assert client.delete(f"/analyses/{aid}/references/{rid}").status_code == 204
        assert client.get(f"/analyses/{aid}/references").json() == {"reference_ids": []}

    def test_reverse_lookup(self, client: TestClient) -> None:
        a = make_analysis(client, title="A")
        ref = make_reference(client)
        client.post(f"/analyses/{a['id']}/references", json={"reference_id": ref["id"]})

        touching = client.get(f"/analyses/for-reference/{ref['id']}").json()
        assert {x["id"] for x in touching} == {a["id"]}


class TestAnalysisLinks:
    def test_add_list_remove(self, client: TestClient) -> None:
        a = make_analysis(client, title="A")
        b = make_analysis(client, title="B")
        resp = client.post(f"/analyses/{a['id']}/links", json={"linked_analysis_id": b["id"]})
        assert resp.status_code == 204
        assert client.get(f"/analyses/{a['id']}/links").json() == {"analysis_ids": [b["id"]]}

        assert client.delete(f"/analyses/{a['id']}/links/{b['id']}").status_code == 204
        assert client.get(f"/analyses/{a['id']}/links").json() == {"analysis_ids": []}

    def test_self_link_returns_422(self, client: TestClient) -> None:
        a = make_analysis(client)
        resp = client.post(f"/analyses/{a['id']}/links", json={"linked_analysis_id": a["id"]})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"


class TestAnalysisNotes:
    def test_create_and_list_analysis_notes(self, client: TestClient) -> None:
        created = make_analysis(client)
        resp = client.post(
            "/notes",
            json={
                "analysis_id": created["id"],
                "title": "Assumption check",
                "body": "Revisit growth rate.",
                "tags": ["assumptions"],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["ticker"] is None
        assert body["reference_id"] is None
        assert body["analysis_id"] == created["id"]

        listed = client.get(f"/analyses/{created['id']}/notes")
        assert [n["id"] for n in listed.json()] == [body["id"]]
