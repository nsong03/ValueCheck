"""References endpoints: the knowledge library CRUD, scan, and file/URL open."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def make_reference(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": "webpage",
        "title": "An Article",
        "location": "https://example.com/a",
    }
    payload.update(overrides)
    resp = client.post("/references", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestReferencesCrud:
    def test_create_and_get(self, client: TestClient) -> None:
        created = make_reference(client)
        got = client.get(f"/references/{created['id']}")
        assert got.status_code == 200
        assert got.json() == created

    def test_list_all(self, client: TestClient) -> None:
        make_reference(client, title="A", location="https://x/a")
        make_reference(client, title="B", location="https://x/b")
        listed = client.get("/references").json()
        assert {r["title"] for r in listed} == {"A", "B"}

    def test_duplicate_location_is_conflict(self, client: TestClient) -> None:
        make_reference(client, location="https://x/dup")
        resp = client.post(
            "/references",
            json={"kind": "webpage", "title": "Again", "location": "https://x/dup"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "conflict"

    def test_update(self, client: TestClient) -> None:
        created = make_reference(client)
        resp = client.patch(f"/references/{created['id']}", json={"title": "Revised"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Revised"
        assert resp.json()["kind"] == created["kind"]  # untouched

    def test_update_missing_returns_404(self, client: TestClient) -> None:
        resp = client.patch("/references/999", json={"title": "x"})
        assert resp.status_code == 404

    def test_delete(self, client: TestClient) -> None:
        created = make_reference(client)
        assert client.delete(f"/references/{created['id']}").status_code == 204
        assert client.get(f"/references/{created['id']}").status_code == 404

    def test_validation_envelope(self, client: TestClient) -> None:
        resp = client.post("/references", json={"kind": "", "title": "", "location": ""})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"


class TestScanEndpoint:
    def test_scan_with_no_library_configured_is_a_noop(self, client: TestClient) -> None:
        resp = client.post("/references/scan")
        assert resp.status_code == 200
        assert resp.json() == {"created": []}


class TestFileEndpoint:
    def test_url_reference_redirects(self, client: TestClient) -> None:
        created = make_reference(client, location="https://example.com/some-article")
        resp = client.get(f"/references/{created['id']}/file", follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert resp.headers["location"] == "https://example.com/some-article"

    def test_local_file_is_streamed(self, client: TestClient, tmp_path: Path) -> None:
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake content")
        created = make_reference(client, kind="pdf", location=str(pdf))

        resp = client.get(f"/references/{created['id']}/file")
        assert resp.status_code == 200
        assert resp.content == b"%PDF-1.4 fake content"

    def test_missing_local_file_returns_404(self, client: TestClient) -> None:
        created = make_reference(client, kind="pdf", location="C:/does/not/exist.pdf")
        resp = client.get(f"/references/{created['id']}/file")
        assert resp.status_code == 404

    def test_missing_reference_returns_404(self, client: TestClient) -> None:
        resp = client.get("/references/999/file")
        assert resp.status_code == 404
