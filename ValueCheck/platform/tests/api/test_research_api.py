"""Notes + tags endpoints: persist/reload, server-side canonicalization, merge."""

from __future__ import annotations

from fastapi.testclient import TestClient


def make_note(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ticker": "DEMO",
        "title": "Thesis",
        "body": "Wide moat, sticky ecosystem.",
        "tags": ["Wide Moat", "hardware"],
    }
    payload.update(overrides)
    resp = client.post("/notes", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestNotesCrud:
    def test_create_canonicalizes_tags_server_side(self, client: TestClient) -> None:
        body = make_note(client, tags=["Wide Moat", "wide_moat", "AI/ML"])
        assert body["tags"] == ["ai-ml", "wide-moat"]  # canonical + deduped
        assert body["id"] >= 1
        assert body["created_at"] == body["updated_at"]

    def test_persists_and_reloads(self, client: TestClient) -> None:
        created = make_note(client)
        got = client.get(f"/notes/{created['id']}")
        assert got.status_code == 200
        assert got.json() == created

        listed = client.get("/companies/DEMO/notes")
        assert [n["id"] for n in listed.json()] == [created["id"]]

    def test_update(self, client: TestClient) -> None:
        created = make_note(client)
        resp = client.put(
            f"/notes/{created['id']}",
            json={"title": "Revised", "body": "New body", "tags": ["New Tag"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Revised"
        assert body["tags"] == ["new-tag"]
        assert body["created_at"] == created["created_at"]

    def test_delete(self, client: TestClient) -> None:
        created = make_note(client)
        assert client.delete(f"/notes/{created['id']}").status_code == 204
        assert client.get(f"/notes/{created['id']}").status_code == 404
        assert client.delete(f"/notes/{created['id']}").status_code == 404

    def test_validation_envelope(self, client: TestClient) -> None:
        resp = client.post("/notes", json={"ticker": "DEMO", "title": "", "body": ""})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"


class TestTags:
    def test_vocabulary_for_autocomplete(self, client: TestClient) -> None:
        assert client.get("/tags").json() == {"tags": []}
        make_note(client, tags=["beta", "Alpha"])
        make_note(client, tags=["alpha", "gamma"])
        assert client.get("/tags").json() == {"tags": ["alpha", "beta", "gamma"]}

    def test_merge_endpoint(self, client: TestClient) -> None:
        first = make_note(client, tags=["semis"])
        make_note(client, tags=["semiconductors"])

        resp = client.post("/tags/merge", json={"source": "Semis", "target": "semiconductors"})
        assert resp.status_code == 200
        assert resp.json() == {
            "source": "semis",
            "target": "semiconductors",
            "notes_affected": 1,
        }
        assert client.get("/tags").json() == {"tags": ["semiconductors"]}
        assert client.get(f"/notes/{first['id']}").json()["tags"] == ["semiconductors"]

    def test_merge_same_tag_rejected(self, client: TestClient) -> None:
        resp = client.post("/tags/merge", json={"source": "Wide Moat", "target": "wide-moat"})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"
