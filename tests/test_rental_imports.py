from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from realtykit.ingest.rentals import RentalImportError, import_rentals
from realtykit.settings import Settings
from realtykit.store.db import init_db
from realtykit.store.rentals import list_rental_observations, rental_trends

TODAY = datetime.now(UTC).date()


def _connection(tmp_path):
    settings = Settings(_env_file=None, REALTYKIT_DATA_DIR=tmp_path)
    return init_db(settings=settings)


def _row(**overrides):
    payload = {
        "observation_id": "rent:test:1",
        "source": "user research export",
        "observed_on": TODAY.isoformat(),
        "city": "San Jose",
        "zip_code": "95113",
        "neighborhood": "Downtown",
        "monthly_rent": 3200,
        "bedrooms": 1,
        "bathrooms": 1,
        "property_type": "apartment",
        "listing_status": "new",
        "sqft": 700,
        "year_built": 2018,
        "amenities": ["parking", "pool"],
    }
    payload.update(overrides)
    return payload


def _json_import(conn, rows, filename="rentals.json"):
    return import_rentals(
        filename=filename,
        file_format="json",
        content=json.dumps(rows),
        conn=conn,
    )


def test_json_import_is_idempotent_and_updates_by_observation_id(tmp_path):
    conn = _connection(tmp_path)
    try:
        first = _json_import(conn, [_row()])
        second = _json_import(
            conn,
            [_row(monthly_rent=3350)],
            filename="rentals-corrected.json",
        )
        observations, total = list_rental_observations(
            conn, city="San Jose", limit=10, offset=0
        )
    finally:
        conn.close()

    assert first["inserted"] == 1
    assert first["updated"] == 0
    assert second["inserted"] == 0
    assert second["updated"] == 1
    assert total == 1
    assert observations[0]["monthly_rent"] == 3350
    assert observations[0]["amenities"] == ["parking", "pool"]
    assert observations[0]["import_id"] == second["import_id"]


def test_csv_import_normalizes_supported_labels_and_derives_stable_ids(tmp_path):
    conn = _connection(tmp_path)
    content = (
        "observed_on,city,monthly_rent,bedrooms,property_type,listing_status,amenities\n"
        f"{TODAY.isoformat()},mountain view,5200,2,townhome,old,garage|laundry\n"
    )
    try:
        first = import_rentals(
            filename="rents.csv", file_format="csv", content=content, conn=conn
        )
        second = import_rentals(
            filename="rents.csv", file_format="csv", content=content, conn=conn
        )
        observations, total = list_rental_observations(
            conn, city="Mountain View", limit=10, offset=0
        )
    finally:
        conn.close()

    assert first["inserted"] == 1
    assert second["updated"] == 1
    assert total == 1
    assert observations[0]["property_type"] == "townhouse"
    assert observations[0]["listing_status"] == "existing"
    assert observations[0]["observation_id"].startswith("local:")


def test_invalid_row_rejects_entire_import_without_writes(tmp_path):
    conn = _connection(tmp_path)
    too_old = (TODAY - timedelta(days=366 * 3 + 1)).isoformat()
    try:
        with pytest.raises(RentalImportError) as exc_info:
            _json_import(
                conn,
                [
                    _row(),
                    _row(
                        observation_id="rent:test:2",
                        city="San Francisco",
                        observed_on=too_old,
                    ),
                ],
            )
        count = conn.execute("SELECT COUNT(*) FROM rental_observations").fetchone()[0]
    finally:
        conn.close()

    assert count == 0
    assert exc_info.value.errors[0]["row"] == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("monthly_rent", True),
        ("bedrooms", True),
        ("bathrooms", False),
        ("sqft", True),
        ("year_built", False),
    ],
)
def test_json_booleans_are_not_accepted_as_numbers(tmp_path, field, value):
    conn = _connection(tmp_path)
    try:
        with pytest.raises(RentalImportError):
            _json_import(conn, [_row(**{field: value})])
    finally:
        conn.close()


def test_existing_id_cannot_be_moved_to_a_different_observation_event(tmp_path):
    conn = _connection(tmp_path)
    original = _row()
    try:
        _json_import(conn, [original])
        with pytest.raises(RentalImportError) as exc_info:
            _json_import(
                conn,
                [_row(city="Sunnyvale")],
                filename="conflicting-event.json",
            )
        stored = conn.execute(
            "SELECT city, monthly_rent FROM rental_observations WHERE observation_id = ?",
            (original["observation_id"],),
        ).fetchone()
        import_count = conn.execute("SELECT COUNT(*) FROM rental_imports").fetchone()[0]
    finally:
        conn.close()

    assert "different event" in str(exc_info.value)
    assert dict(stored) == {"city": "San Jose", "monthly_rent": 3200}
    assert import_count == 1


def test_observation_listing_tolerates_malformed_legacy_amenities(tmp_path):
    conn = _connection(tmp_path)
    try:
        _json_import(conn, [_row()])
        conn.execute(
            "UPDATE rental_observations SET amenities_json = ?",
            ("not-json",),
        )
        conn.commit()
        observations, _ = list_rental_observations(
            conn, city="San Jose", limit=10, offset=0
        )
    finally:
        conn.close()

    assert observations[0]["amenities"] == []


@pytest.mark.parametrize(
    ("filename", "file_format", "content"),
    [
        ("../rentals.json", "json", "[]"),
        ("rentals.csv", "json", "[]"),
        ("rentals.json", "json", '[{"unexpected": true}]'),
    ],
)
def test_import_rejects_paths_mismatches_and_unknown_fields(
    tmp_path, filename, file_format, content
):
    conn = _connection(tmp_path)
    try:
        with pytest.raises(RentalImportError):
            import_rentals(
                filename=filename,
                file_format=file_format,
                content=content,
                conn=conn,
            )
    finally:
        conn.close()


def test_trends_segment_month_bedrooms_property_type_and_listing_status(tmp_path):
    conn = _connection(tmp_path)
    as_of = TODAY
    previous_month = (as_of.replace(day=1) - timedelta(days=1)).replace(day=10)
    rows = [
        _row(observation_id="r1", observed_on=as_of.isoformat(), monthly_rent=3000),
        _row(observation_id="r2", observed_on=as_of.isoformat(), monthly_rent=3400),
        _row(
            observation_id="r3",
            observed_on=as_of.isoformat(),
            monthly_rent=5100,
            bedrooms=2,
            property_type="single_family",
            listing_status="existing",
        ),
        _row(
            observation_id="r4",
            observed_on=previous_month.isoformat(),
            monthly_rent=4100,
            property_type="townhouse",
        ),
        _row(
            observation_id="other-city",
            observed_on=as_of.isoformat(),
            city="Sunnyvale",
            monthly_rent=9999,
        ),
    ]
    try:
        _json_import(conn, rows)
        trend = rental_trends(conn, city="San Jose", months=12, as_of=as_of)
    finally:
        conn.close()

    assert trend["observation_count"] == 4
    segments = {
        (item["month"], item["bedrooms"], item["property_type"], item["listing_status"]): item
        for item in trend["segments"]
    }
    apartment = segments[(as_of.strftime("%Y-%m"), 1, "apartment", "new")]
    assert apartment["count"] == 2
    assert apartment["median_rent"] == 3200
    assert apartment["average_rent"] == 3200
    assert len(segments) == 3


def test_rental_api_import_and_trend_contract(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from realtykit.api.deps import db_conn, ensure_local_request
    from realtykit.api.main import app

    def override_db():
        conn = _connection(tmp_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[db_conn] = override_db
    app.dependency_overrides[ensure_local_request] = lambda: None
    client = TestClient(app)
    try:
        imported = client.post(
            "/api/rentals/import",
            json={
                "filename": "rentals.json",
                "format": "json",
                "content": json.dumps([_row()]),
            },
        )
        trend = client.get("/api/rentals/trends", params={"city": "San Jose"})
        future_trend = client.get(
            "/api/rentals/trends",
            params={"city": "San Jose", "as_of": (TODAY + timedelta(days=1)).isoformat()},
        )
        listed = client.get("/api/rentals/observations", params={"city": "San Jose"})
    finally:
        app.dependency_overrides.clear()

    assert imported.status_code == 200
    assert imported.json()["inserted"] == 1
    assert trend.status_code == 200
    assert trend.json()["segments"][0]["listing_status"] == "new"
    assert future_trend.status_code == 422
    assert future_trend.json()["error"]["code"] == "invalid_as_of"
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_rental_import_route_rejects_non_loopback_client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from realtykit.api.main import app

    client = TestClient(app, client=("192.0.2.10", 50000))
    response = client.post(
        "/api/rentals/import",
        json={"filename": "rentals.json", "format": "json", "content": "[]"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "loopback_only"
