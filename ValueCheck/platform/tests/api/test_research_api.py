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


class TestReferenceScopedNotes:
    """A note attaches to a company OR a reference (Phase 9b)."""

    def make_reference(self, client: TestClient) -> int:
        resp = client.post(
            "/references",
            json={"kind": "book", "title": "A Book", "location": "https://example.com/book"},
        )
        assert resp.status_code == 201, resp.text
        ref_id: int = resp.json()["id"]
        return ref_id

    def test_create_and_list_reference_notes(self, client: TestClient) -> None:
        ref_id = self.make_reference(client)
        resp = client.post(
            "/notes",
            json={"reference_id": ref_id, "title": "Ch. 1", "body": "Thoughts.", "tags": ["value"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["ticker"] is None
        assert body["reference_id"] == ref_id

        listed = client.get(f"/references/{ref_id}/notes")
        assert [n["id"] for n in listed.json()] == [body["id"]]

    def test_neither_subject_is_a_validation_error(self, client: TestClient) -> None:
        resp = client.post("/notes", json={"title": "t", "body": "", "tags": []})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    def test_both_subjects_is_a_validation_error(self, client: TestClient) -> None:
        ref_id = self.make_reference(client)
        resp = client.post(
            "/notes",
            json={"ticker": "DEMO", "reference_id": ref_id, "title": "t", "body": "", "tags": []},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    def test_links_round_trip(self, client: TestClient) -> None:
        created = make_note(
            client,
            links=[{"label": "Damodaran on WACC", "url": "https://example.com/wacc"}],
        )
        assert created["links"] == [
            {"label": "Damodaran on WACC", "url": "https://example.com/wacc"}
        ]
        got = client.get(f"/notes/{created['id']}")
        assert got.json()["links"] == created["links"]

    def test_update_replaces_links(self, client: TestClient) -> None:
        created = make_note(client)
        resp = client.put(
            f"/notes/{created['id']}",
            json={
                "title": "T",
                "body": "",
                "tags": [],
                "links": [{"label": "new", "url": "https://new.example"}],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["links"] == [{"label": "new", "url": "https://new.example"}]


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
