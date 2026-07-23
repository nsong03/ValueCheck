"""Attribute endpoints: schema-on-write definitions, values, and history."""

from __future__ import annotations

from fastapi.testclient import TestClient


def set_attribute(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"key": "region", "value": "china", "source": "note"}
    payload.update(overrides)
    resp = client.post("/companies/DEMO/attributes", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestSetAttribute:
    def test_first_use_creates_definition_and_returns_stored_value(
        self, client: TestClient
    ) -> None:
        body = set_attribute(
            client, key="Quality.Moat", value="4", value_type="scale", source="note"
        )
        assert body["key"] == "quality.moat"
        assert body["value"] == "4"
        assert body["source"] == "note"
        assert body["id"] >= 1

        defs = client.get("/attributes/definitions").json()
        assert defs[0]["key"] == "quality.moat"
        assert defs[0]["value_type"] == "scale"
        assert (defs[0]["scale_min"], defs[0]["scale_max"]) == (1.0, 5.0)

    def test_scale_out_of_range_returns_422(self, client: TestClient) -> None:
        set_attribute(client, key="quality.moat", value="4", value_type="scale")
        resp = client.post(
            "/companies/DEMO/attributes",
            json={"key": "quality.moat", "value": "9", "source": "grid"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    def test_grid_edit_has_no_note_but_may_carry_a_reason(self, client: TestClient) -> None:
        body = set_attribute(
            client, key="status", value="avoid", source="grid", reason="Margins collapsing"
        )
        assert body["source"] == "grid"
        assert body["note_id"] is None
        assert body["reason"] == "Margins collapsing"


class TestCurrentAndHistory:
    def test_current_values_for_company(self, client: TestClient) -> None:
        set_attribute(client, value="china")
        current = client.get("/companies/DEMO/attributes").json()
        assert current["region"]["value"] == "china"

    def test_current_values_scoped_per_ticker(self, client: TestClient) -> None:
        set_attribute(client)
        client.post(
            "/companies/OTHER/attributes",
            json={"key": "region", "value": "us", "source": "note"},
        )
        assert client.get("/companies/OTHER/attributes").json()["region"]["value"] == "us"
        assert client.get("/companies/DEMO/attributes").json()["region"]["value"] == "china"

    def test_history_newest_first(self, client: TestClient) -> None:
        set_attribute(client, value="us")
        set_attribute(client, value="china", source="grid")
        history = client.get("/companies/DEMO/attributes/region/history").json()
        assert history["ticker"] == "DEMO"
        assert history["key"] == "region"
        assert [v["value"] for v in history["values"]] == ["china", "us"]

    def test_history_empty_for_unknown_key(self, client: TestClient) -> None:
        history = client.get("/companies/DEMO/attributes/ghost/history").json()
        assert history["values"] == []


class TestCurateDefinition:
    def test_curate_enum_with_allowed_values_and_colors(self, client: TestClient) -> None:
        set_attribute(client, key="status", value="avoid", source="grid")
        resp = client.patch(
            "/attributes/definitions/status",
            json={
                "allowed_values": ["avoid", "good-company"],
                "colors": {"avoid": "#ef4444", "good-company": "#22c55e"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["allowed_values"] == ["avoid", "good-company"]
        assert body["colors"] == {"avoid": "#ef4444", "good-company": "#22c55e"}

    def test_curate_unknown_key_returns_404(self, client: TestClient) -> None:
        resp = client.patch("/attributes/definitions/ghost", json={"label": "Ghost"})
        assert resp.status_code == 404
