from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from realtykit.ingest.rental_collection import collect_rentcast
from realtykit.providers import rentcast, zillow_research
from realtykit.settings import Settings
from realtykit.store.db import init_db
from realtykit.store.facts import upsert_facts, upsert_geos
from realtykit.store.rentals import rental_trends

TODAY = datetime.now(UTC).date()


def _month_start(value: date, months_back: int) -> date:
    index = value.year * 12 + value.month - 1 - months_back
    return date(index // 12, index % 12 + 1, 1)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def _settings(path: Path) -> Settings:
    return Settings(_env_file=None, REALTYKIT_DATA_DIR=path, RENTCAST_API_KEY="test-only")


def test_rentcast_city_collection_sanitizes_and_expands_rental_history(monkeypatch, tmp_path):
    listed = (TODAY - timedelta(days=10)).isoformat()
    old_listed = (TODAY - timedelta(days=100)).isoformat()
    removed = (TODAY - timedelta(days=50)).isoformat()
    payload = [
        {
            "id": "provider-property-1",
            "formattedAddress": "discarded",
            "city": "San Jose",
            "state": "CA",
            "zipCode": "95113",
            "latitude": 37.33,
            "longitude": -121.89,
            "propertyType": "Apartment",
            "bedrooms": 2,
            "bathrooms": 1,
            "squareFootage": 900,
            "yearBuilt": 2019,
            "status": "Active",
            "price": 3600,
            "listedDate": listed,
            "lastSeenDate": TODAY.isoformat(),
            "daysOnMarket": 10,
            "listingAgent": {"name": "discarded", "email": "discarded@example.test"},
            "mlsName": "discarded",
            "history": {
                old_listed: {
                    "event": "Rental Listing",
                    "price": 3300,
                    "listedDate": old_listed,
                    "removedDate": removed,
                    "daysOnMarket": 50,
                },
                "sale": {"event": "Sale Listing", "price": 900000, "listedDate": old_listed},
            },
        },
        {
            "id": "wrong-city",
            "city": "San Francisco",
            "state": "CA",
            "propertyType": "Apartment",
            "bedrooms": 2,
            "price": 9999,
            "listedDate": listed,
        },
    ]
    captured = {}
    monkeypatch.setattr(rentcast, "get_cached", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        rentcast,
        "_request",
        lambda _url, params, _settings: captured.setdefault("params", params)
        and FakeResponse(payload),
    )
    monkeypatch.setattr(
        rentcast, "put_cached", lambda _provider, _key, rows, _settings: captured.update(rows=rows)
    )

    rows, cached = rentcast.fetch_city_rentals(
        city="San Jose", status="active", limit=25, settings=_settings(tmp_path)
    )

    assert cached is False
    assert len(rows) == 2
    assert captured["params"]["status"] == "Active"
    assert captured["params"]["bedrooms"] == "1:3"
    assert captured["params"]["limit"] == 25
    assert {row["availability_status"] for row in rows} == {"active", "inactive"}
    assert {row["listing_status"] for row in rows} == {"new", "existing"}
    assert all("formattedAddress" not in row for row in rows)
    assert all("listingAgent" not in row for row in rows)
    assert all("mlsName" not in row for row in rows)
    assert captured["rows"] == rows


def test_bounded_collector_persists_each_city_status_batch(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    conn = init_db(settings=settings)
    calls = []

    def fake_fetch(*, city, status, **_kwargs):
        calls.append((city, status))
        return (
            [
                {
                    "observation_id": f"provider:{city.lower().replace(' ', '-')}:{status}",
                    "source": "rentcast_api",
                    "observed_on": TODAY.isoformat(),
                    "city": city,
                    "monthly_rent": 4000,
                    "bedrooms": 2,
                    "property_type": "apartment",
                    "listing_status": "new",
                    "availability_status": status,
                }
            ],
            False,
        )

    monkeypatch.setattr(rentcast, "fetch_city_rentals", fake_fetch)
    try:
        result = collect_rentcast(
            conn,
            settings=settings,
            cities=("San Jose", "Sunnyvale"),
            statuses=("active", "inactive"),
            limit_per_query=20,
        )
        count = conn.execute("SELECT COUNT(*) FROM rental_observations").fetchone()[0]
    finally:
        conn.close()

    assert calls == [
        ("San Jose", "active"),
        ("San Jose", "inactive"),
        ("Sunnyvale", "active"),
        ("Sunnyvale", "inactive"),
    ]
    assert count == 4
    assert result["inserted"] == 4
    assert len(result["queries"]) == 4


def test_zori_ingest_filters_target_cities_and_exposes_separate_index(tmp_path):
    settings = Settings(_env_file=None, REALTYKIT_DATA_DIR=tmp_path)
    conn = init_db(settings=settings)
    current_month = TODAY.replace(day=1)
    previous_month = (current_month - timedelta(days=1)).replace(day=1)
    csv_path = tmp_path / "zori.csv"
    csv_path.write_text(
        "RegionID,SizeRank,RegionName,RegionType,StateName,"
        f"{previous_month.isoformat()},{current_month.isoformat()}\n"
        f"1,1,San Jose,city,CA,3100,3200\n"
        f"2,2,Sunnyvale,city,CA,3300,3400\n"
        f"3,3,Mountain View,city,CA,3500,3600\n"
        f"4,4,Palo Alto,city,CA,3700,3800\n"
        f"5,5,San Francisco,city,CA,3900,4000\n"
        f"6,6,San Jose,city,TX,1000,1100\n",
        encoding="utf-8",
    )
    cached = SimpleNamespace(
        path=csv_path,
        fetched_at=f"{TODAY.isoformat()}T00:00:00Z",
        last_modified=None,
        etag=None,
        content_sha256="fixture-sha",
        bytes=csv_path.stat().st_size,
    )
    fake_http = SimpleNamespace(get_cached=lambda *_args, **_kwargs: cached)
    spec = next(
        item for item in zillow_research.DATASETS if item["source_id"] == zillow_research.ZORI_SOURCE_ID
    )
    try:
        outcome = zillow_research._ingest_one(conn, fake_http, spec, False)
        trend = rental_trends(conn, city="San Jose", months=12)
        facts = conn.execute(
            "SELECT COUNT(*) FROM market_facts WHERE metric = 'zori_all'"
        ).fetchone()[0]
    finally:
        conn.close()

    assert outcome.status == "ok"
    assert outcome.rows_upserted == 8
    assert facts == 8
    assert trend["segments"] == []
    assert trend["market_indices"] == [
        {
            "provider": "zillow",
            "source_id": "zillow:zori_city_all",
            "metric": "zori",
            "home_type": "all_homes",
            "city": "San Jose",
            "as_of": current_month.isoformat(),
            "points": [
                {"month": previous_month.strftime("%Y-%m"), "value": 3100.0},
                {"month": current_month.strftime("%Y-%m"), "value": 3200.0},
            ],
        }
    ]


def test_rental_history_returns_requested_months_for_only_the_selected_city(tmp_path):
    conn = init_db(settings=Settings(_env_file=None, REALTYKIT_DATA_DIR=tmp_path))
    as_of = date(2026, 7, 31)
    geos = [
        {"geo_id": "zillow:city:sj", "level": "city", "name": "San Jose", "state": "CA"},
        {
            "geo_id": "zillow:city:sunnyvale",
            "level": "city",
            "name": "Sunnyvale",
            "state": "CA",
        },
    ]
    facts = []
    for months_back in range(30):
        period = _month_start(as_of, months_back).isoformat()
        facts.extend(
            [
                {
                    "geo_id": "zillow:city:sj",
                    "period_end": period,
                    "cadence": "monthly",
                    "metric": "zori_all",
                    "value": 3000 + months_back,
                    "provider": "zillow",
                    "source_id": "zillow:zori_city_all",
                },
                {
                    "geo_id": "zillow:city:sunnyvale",
                    "period_end": period,
                    "cadence": "monthly",
                    "metric": "zori_all",
                    "value": 4000 + months_back,
                    "provider": "zillow",
                    "source_id": "zillow:zori_city_all",
                },
            ]
        )
    try:
        upsert_geos(geos, conn)
        upsert_facts(facts, conn)
        conn.commit()
        result = rental_trends(conn, city="Sunnyvale", months=24)
    finally:
        conn.close()

    assert result["months"] == 24
    assert len(result["market_indices"]) == 1
    index = result["market_indices"][0]
    assert index["city"] == "Sunnyvale"
    assert len(index["points"]) == 24
    assert all(point["value"] >= 4000 for point in index["points"])
