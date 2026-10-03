"""Local browser request boundaries and private-input error handling."""

import pytest
from fastapi.testclient import TestClient

from realtykit.api.main import app
from realtykit.api.routes import ingest
from realtykit.api.routes import map as map_routes
from realtykit.settings import Settings


def test_foreign_origin_cannot_trigger_refresh(monkeypatch):
    def unexpected_refresh(**_kwargs):
        raise AssertionError("foreign-origin request must not reach providers")

    monkeypatch.setattr(ingest, "refresh", unexpected_refresh)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
        for origin in ("https://untrusted.example", "null"):
            response = client.post("/api/ingest/refresh", headers={"Origin": origin})
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "untrusted_origin"


def test_trusted_browser_and_cli_can_refresh(monkeypatch):
    calls = []

    def local_refresh(**kwargs):
        calls.append(kwargs)
        return {"run_id": "security-test", "ok": True, "outcomes": []}

    monkeypatch.setattr(ingest, "refresh", local_refresh)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
        for headers in ({}, {"Origin": "http://127.0.0.1:5173"}, {"Origin": "http://127.0.0.1"}):
            response = client.post("/api/ingest/refresh", headers=headers)
            assert response.status_code == 200
    assert len(calls) == 3


@pytest.mark.parametrize("endpoint", ["listings", "sales"])
def test_cross_site_browser_get_cannot_consume_provider_quota(monkeypatch, endpoint):
    def unexpected_provider(**_kwargs):
        raise AssertionError("cross-site browser GET must not reach providers")

    monkeypatch.setattr(
        map_routes, "get_settings", lambda: Settings(_env_file=None, rentcast_api_key="test")
    )
    monkeypatch.setattr(map_routes.rentcast, "fetch_bbox", unexpected_provider)
    monkeypatch.setattr(map_routes.rentcast, "fetch_sold_bbox", unexpected_provider)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
        response = client.get(
            f"/api/map/{endpoint}",
            params={"bbox": "-122.2,37.4,-122.1,37.5"},
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "untrusted_origin"


def test_validation_does_not_echo_private_input():
    marker = "PRIVATE_INPUT_SECURITY_PROBE"
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
        response = client.get("/api/trends", params={"cadence": marker})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"
        assert marker not in response.text
        response = client.post(
            "/api/rentals/import",
            json={"filename": "private.json", "format": marker, "content": marker},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"
        assert marker not in response.text


@pytest.mark.parametrize(
    "endpoint,provider_method",
    [
        ("listings", "fetch_bbox"),
        ("sales", "fetch_sold_bbox"),
    ],
)
@pytest.mark.parametrize("error_type", [ValueError, RuntimeError])
def test_provider_errors_do_not_echo_private_details(
    monkeypatch, endpoint, provider_method, error_type
):
    marker = "PRIVATE_PROVIDER_SECURITY_PROBE"

    def fail_provider(**_kwargs):
        raise error_type(marker)

    monkeypatch.setattr(
        map_routes, "get_settings", lambda: Settings(_env_file=None, rentcast_api_key="test")
    )
    monkeypatch.setattr(map_routes.rentcast, provider_method, fail_provider)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
        response = client.get(f"/api/map/{endpoint}", params={"bbox": "-122.2,37.4,-122.1,37.5"})
        assert response.status_code == 502
        assert marker not in response.text
