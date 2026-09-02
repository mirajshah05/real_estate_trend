"""API contract: health + freshness shape via TestClient (in-process, no network).

Skips when the FastAPI app is not importable yet (Agent A has not landed).
"""

from __future__ import annotations

import pytest

KNOWN_FRESHNESS_STATUS = {
    "live",
    "fresh",
    "aging",
    "stale",
    "by_design_monthly",
    "unavailable",
}


def _load_app():
    try:
        from realtykit.api.main import app
    except ImportError:
        pytest.skip("realtykit.api.main.app is not importable yet")
    return app


def _client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    return TestClient(_load_app())


def test_health_shape():
    client = _client()
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert body.get("ok") is True or str(body.get("status", "")).lower() in {
        "ok",
        "healthy",
    }
    if "service" in body:
        assert body["service"] == "realtykit"


def test_freshness_shape():
    client = _client()
    response = client.get("/api/freshness")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    block = body["freshness"] if "freshness" in body else body
    assert isinstance(block, dict)
    if "overall" in block:
        assert str(block["overall"]) in KNOWN_FRESHNESS_STATUS
    if "computed_at" in block:
        assert isinstance(block["computed_at"], str)
        assert block["computed_at"]
    sources = block.get("sources", body.get("sources", []))
    assert isinstance(sources, list)
    for src in sources:
        assert isinstance(src, dict)
        # Dual clocks: only assert keys that the payload already has.
        if "as_of" in src:
            assert src["as_of"] is None or isinstance(src["as_of"], str)
        if "observation_as_of" in src:
            assert src["observation_as_of"] is None or isinstance(
                src["observation_as_of"], str
            )
        if "http_last_modified" in src:
            assert src["http_last_modified"] is None or isinstance(
                src["http_last_modified"], str
            )
        if "status" in src:
            assert str(src["status"]) in KNOWN_FRESHNESS_STATUS


def test_government_area_shape():
    client = _client()
    response = client.get("/api/map/government-areas")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("features"), list)
    assert "sale prices" in body.get("note", "").lower()
    for feature in body["features"]:
        assert feature["county"] == "Santa Clara"
        assert feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
        assert feature["parent_geo_id"]


def test_stock_dips_declares_recent_history_scope():
    client = _client()
    response = client.get("/api/stocks/dips")
    assert response.status_code == 200
    body = response.json()
    assert body["lookback_days"] == 365
    assert body["threshold_window_weeks"] == 52
    assert isinstance(body["history_points"], int)
    assert "not an all-history crisis list" in body["note"]
    assert "2008" in body["note"]
