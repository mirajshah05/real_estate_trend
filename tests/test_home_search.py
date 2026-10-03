from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from realtykit.api.main import app
from realtykit.api.routes import homes
from realtykit.api.routes import map as map_routes
from realtykit.providers import home_search
from realtykit.settings import Settings
from realtykit.store.db import connect, init_db


def property_row(**changes):
    return {
        "id": "test-home",
        "formattedAddress": "100 Test St",
        "latitude": 30.27,
        "longitude": -97.74,
        "propertyType": "Single Family",
        "status": "Active",
        "price": 500000,
        "bedrooms": 3,
        "bathrooms": 2,
        "squareFootage": 1500,
        "lastSeenDate": datetime.now(UTC).date().isoformat(),
        "owner": {"name": "PRIVATE_OWNER"},
        "listingAgent": {"email": "PRIVATE_AGENT"},
        **changes,
    }


def criteria(**changes):
    return homes.HomeSearchRequest(
        lat=30.27,
        lon=-97.74,
        min_beds=3,
        max_price=600000,
        property_type="Single Family",
        **changes,
    ).model_dump()


def test_matches_enforce_radius_filters_status_missing_facts_and_privacy():
    records = [
        property_row(),
        property_row(id="far", latitude=31),
        property_row(id="over-budget", price=700000),
        property_row(id="missing", price=None),
        property_row(id="small", bedrooms=2),
        property_row(id="wrong-type", propertyType="Condo"),
        property_row(id="inactive", status="Inactive"),
        property_row(id="invalid", latitude="NaN"),
        property_row(id="undated", lastSeenDate=None),
        property_row(),
    ]
    rows = home_search.match_rows(records, criteria())
    assert len(rows) == 1
    assert rows[0]["distance_miles"] == 0
    assert "Meets your budget" in rows[0]["match_reasons"]
    assert "PRIVATE" not in str(rows)
    assert "owner" not in rows[0] and "listingAgent" not in rows[0]
    assert home_search.match_rows(records, criteria(exclude_property_id="test-home")) == []


def test_search_builds_provider_ranges_caches_only_sanitized_data(monkeypatch, tmp_path):
    settings = Settings(_env_file=None, REALTYKIT_DATA_DIR=tmp_path, RENTCAST_API_KEY="test")
    conn = connect(settings)
    init_db(conn)
    conn.close()
    calls = []

    def request(url, params, _settings):
        calls.append((url, params))
        return httpx.Response(200, json=[property_row()])

    monkeypatch.setattr(home_search.rentcast, "_request", request)
    result, cached = home_search.search(criteria(intent="rent"), settings)
    assert not cached and result["listings"][0]["intent"] == "rent"
    assert calls[0][0] == home_search.rentcast.RENTAL_URL
    assert calls[0][1]["bedrooms"] == "3.0:*"
    assert calls[0][1]["price"] == "*:600000.0"
    assert calls[0][1]["limit"] == 100
    again, cached = home_search.search(criteria(intent="rent"), settings)
    assert cached and again == result and len(calls) == 1


def test_subject_lookup_discards_owner_and_contacts_before_caching(monkeypatch, tmp_path):
    settings = Settings(_env_file=None, REALTYKIT_DATA_DIR=tmp_path, RENTCAST_API_KEY="test")
    init_db(settings=settings).close()
    calls = []
    monkeypatch.setattr(
        home_search.rentcast,
        "_request",
        lambda url, params, _: calls.append(params) or httpx.Response(200, json=[property_row()]),
    )
    profiles, cached = home_search.subject("100 Test St, Austin TX", settings)
    assert not cached and len(profiles) == 1
    assert "PRIVATE" not in str(profiles)
    conn = connect(settings)
    try:
        payloads = [row[0] for row in conn.execute("SELECT payload_json FROM provider_cache")]
    finally:
        conn.close()
    assert len(payloads) == 1 and "PRIVATE" not in payloads[0]
    again, cached = home_search.subject("100 Test St, Austin TX", settings)
    assert cached and again == profiles and len(calls) == 1


def test_exact_reference_rooms_exclude_larger_smaller_and_missing_categories():
    requirements = homes.HomeSearchRequest(
        lat=30.27,
        lon=-97.74,
        property_type="Single Family",
        min_beds=2,
        max_beds=2,
        min_baths=1,
        max_baths=1,
    ).model_dump()
    records = [
        property_row(id="exact", bedrooms=2, bathrooms=1),
        property_row(id="larger", bedrooms=3, bathrooms=1),
        property_row(id="smaller", bedrooms=1, bathrooms=1),
        property_row(id="more-baths", bedrooms=2, bathrooms=2),
        property_row(id="unknown", bedrooms=None, bathrooms=1),
    ]
    rows = home_search.match_rows(records, requirements)
    assert [row["listing_id"] for row in rows] == ["rentcast:exact"]
    assert "Exactly 2 bedrooms" in rows[0]["match_reasons"]
    assert "Exactly 1 bathrooms" in rows[0]["match_reasons"]
    requirements["max_beds"] = None
    assert len(home_search.match_rows(records, requirements)) == 2


def test_exact_room_query_is_sent_to_provider_not_only_filtered_locally(monkeypatch, tmp_path):
    settings = Settings(_env_file=None, REALTYKIT_DATA_DIR=tmp_path, RENTCAST_API_KEY="test")
    init_db(settings=settings).close()
    calls = []
    monkeypatch.setattr(
        home_search.rentcast,
        "_request",
        lambda url, params, _: calls.append(params) or httpx.Response(200, json=[]),
    )
    home_search.search(
        homes.HomeSearchRequest(
            lat=30.27, lon=-97.74, min_beds=2, max_beds=2, min_baths=1, max_baths=1
        ).model_dump(),
        settings,
    )
    assert calls[0]["bedrooms"] == "2.0:2.0"
    assert calls[0]["bathrooms"] == "1.0:1.0"


@pytest.fixture
def client(monkeypatch, tmp_path):
    settings = Settings(_env_file=None, REALTYKIT_DATA_DIR=tmp_path, RENTCAST_API_KEY="test")
    conn = connect(settings)
    init_db(conn)
    conn.close()
    monkeypatch.setattr(homes, "get_settings", lambda: settings)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as local:
        yield local


def test_search_route_and_private_validation(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        home_search,
        "search",
        lambda body, _settings: (
            calls.append(body) or {"listings": [], "possibly_truncated": False},
            False,
        ),
    )
    response = client.post("/api/homes/search", json={"lat": 30.27, "lon": -97.74})
    assert response.status_code == 200 and response.json()["listings"] == []
    assert len(calls) == 1
    for body in [
        {"lat": 100, "lon": 1},
        {"lat": 30, "lon": -97, "radius": 26},
        {"lat": 30, "lon": -97, "min_price": 100, "max_price": 50},
        {"lat": 30, "lon": -97, "min_beds": 3, "max_beds": 2},
        {"lat": 30, "lon": -97, "min_baths": 2, "max_baths": 1},
        {"lat": 30, "lon": -97, "private_input": "PRIVATE_MARKER"},
    ]:
        response = client.post("/api/homes/search", json=body)
        assert response.status_code == 422 and "PRIVATE_MARKER" not in response.text
    assert len(calls) == 1
    assert (
        client.post(
            "/api/homes/search",
            json={"lat": 30, "lon": -97},
            headers={"Origin": "https://untrusted.example"},
        ).status_code
        == 403
    )
    assert len(calls) == 1


def test_subject_no_result_and_ambiguous_are_actionable(client, monkeypatch):
    monkeypatch.setattr(home_search, "subject", lambda *_: ([], False))
    assert (
        client.post("/api/homes/subject", json={"address": "100 Test St, Austin TX"}).status_code
        == 404
    )
    monkeypatch.setattr(home_search, "subject", lambda *_: ([{}, {}], False))
    assert (
        client.post("/api/homes/subject", json={"address": "100 Test St, Austin TX"}).status_code
        == 409
    )


def test_missing_key_does_not_masquerade_as_no_results(client, monkeypatch):
    settings = Settings(_env_file=None, RENTCAST_API_KEY="")
    monkeypatch.setattr(homes, "get_settings", lambda: settings)
    monkeypatch.setattr(map_routes, "get_settings", lambda: settings)
    assert client.get("/api/homes/status").json()["configured"] is False
    for path, body in [
        ("/api/homes/search", {"lat": 30, "lon": -97}),
        ("/api/homes/subject", {"address": "100 Test St, Austin TX"}),
    ]:
        response = client.post(path, json=body)
        assert (
            response.status_code == 503
            and response.json()["error"]["code"] == "provider_key_missing"
        )
    response = client.get("/api/map/sales?bbox=-98,30,-97,31")
    assert (
        response.status_code == 503 and response.json()["error"]["code"] == "provider_key_missing"
    )


def test_provider_failure_does_not_echo_response_or_key(client, monkeypatch):
    def failed(*_):
        raise httpx.HTTPStatusError(
            "PRIVATE_SECRET",
            request=httpx.Request("GET", "https://example.com"),
            response=httpx.Response(403),
        )

    monkeypatch.setattr(home_search, "search", failed)
    response = client.post("/api/homes/search", json={"lat": 30, "lon": -97})
    assert response.status_code == 502 and "PRIVATE_SECRET" not in response.text
    assert "plan access" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    "endpoint,body,provider_method",
    [
        ("search", {"lat": 30, "lon": -97}, "search"),
        ("subject", {"address": "100 Test St, Austin TX"}, "subject"),
    ],
)
@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://untrusted.example"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_home_endpoints_block_cross_site_provider_requests(
    client, monkeypatch, endpoint, body, provider_method, headers
):
    def unexpected_provider(*_args):
        raise AssertionError("cross-site request must not reach provider")

    monkeypatch.setattr(home_search, provider_method, unexpected_provider)
    response = client.post(f"/api/homes/{endpoint}", json=body, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "untrusted_origin"


def test_sale_evidence_reports_actual_area_window_and_sample_limit(client, monkeypatch):
    monkeypatch.setattr(map_routes, "get_settings", homes.get_settings)
    calls = []

    def fetch(*, west, south, east, north, lookback_days, limit, settings):
        calls.append((west, south, east, north, lookback_days, limit))
        return [], True

    monkeypatch.setattr(map_routes.rentcast, "fetch_sold_bbox", fetch)
    response = client.get("/api/map/sales?bbox=-98,30,-97,31&lookback_days=90&limit=17")
    assert response.status_code == 200
    body = response.json()
    today = datetime.now(UTC).date()
    assert body["query_bounds"] == [-98, 30, -97, 31]
    assert body["record_limit"] == 17
    assert body["date_to"] == today.isoformat()
    assert body["date_from"] == (today - timedelta(days=90)).isoformat()
    assert body["cached"] is True
    assert calls == [(-98, 30, -97, 31, 90, 17)]
