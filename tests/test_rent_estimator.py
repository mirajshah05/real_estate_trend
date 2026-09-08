from __future__ import annotations

import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from realtykit.analysis.rent_estimator import estimate_rent
from realtykit.api.deps import db_conn, ensure_local_request
from realtykit.api.routes.rental_estimate import (
    RentEstimateRequest,
    _load_observations,
    router,
)

TARGET = {
    "city": "San Jose",
    "neighborhood": "Willow Glen",
    "zip_code": "95125",
    "bedrooms": 2,
    "bathrooms": 2,
    "property_type": "apartment",
    "sqft": 1000,
    "year_built": 2015,
    "amenities": ["parking", "in-unit laundry"],
}


def _row(
    ident: str,
    rent: float,
    *,
    observed_on: str = "2026-06-01",
    city: str = "San Jose",
    neighborhood: str = "Willow Glen",
    bedrooms: int = 2,
    bathrooms: float = 2,
    property_type: str = "apartment",
    sqft: float = 1000,
    year_built: int = 2015,
    amenities: list[str] | None = None,
) -> dict:
    return {
        "observation_id": ident,
        "observed_on": observed_on,
        "city": city,
        "zip_code": "95125",
        "neighborhood": neighborhood,
        "monthly_rent": rent,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "property_type": property_type,
        "listing_status": "existing",
        "sqft": sqft,
        "year_built": year_built,
        "amenities": amenities or ["parking", "in-unit laundry"],
    }


def test_exact_comparables_produce_deterministic_estimate_and_range():
    rows = [_row("b", 3900), _row("a", 3800), _row("c", 4000), _row("d", 4100)]
    first = estimate_rent(TARGET, rows, as_of="2026-09-01")
    second = estimate_rent(TARGET, list(reversed(rows)), as_of="2026-09-01")

    assert first == second
    assert first["status"] == "estimated"
    assert first["estimate_monthly_rent"] == 3900
    assert first["range"]["low"] < first["estimate_monthly_rent"]
    assert first["range"]["high"] > first["estimate_monthly_rent"]
    assert first["sample_size"] == 4
    assert "not an appraisal" in first["disclaimer"]


def test_adjusts_smaller_older_comparable_upward_with_explanation():
    result = estimate_rent(
        TARGET,
        [_row("small-old", 3000, bedrooms=1, bathrooms=1, sqft=700, year_built=1980)],
        as_of="2026-09-01",
    )

    assert result["status"] == "low_data"
    assert result["estimate_monthly_rent"] > 3000
    assert result["range"]["high"] > result["range"]["low"]
    assert result["confidence"]["label"] == "low"
    assert {item["factor"] for item in result["adjustments"]} >= {
        "bedrooms",
        "bathrooms",
        "sqft",
        "year_built",
        "location",
        "recency",
    }


def test_sparse_city_pool_backfills_other_city_but_keeps_local_first():
    rows = [
        _row("local", 3800),
        _row("palo", 5000, city="Palo Alto", neighborhood="Downtown"),
        _row("sunny", 4200, city="Sunnyvale", neighborhood="Downtown"),
    ]
    result = estimate_rent(TARGET, rows, as_of="2026-09-01")

    assert result["comparable_pool_size"] == 3
    assert result["comparables"][0]["observation_id"] == "local"
    assert result["confidence"]["score"] < 0.75


def test_invalid_future_stale_and_nonpositive_rows_are_ignored():
    result = estimate_rent(
        TARGET,
        [
            _row("future", 4000, observed_on="2026-10-01"),
            _row("stale", 3500, observed_on="2022-01-01"),
            _row("zero", 0),
        ],
        as_of="2026-09-01",
    )

    assert result["status"] == "no_data"
    assert result["estimate_monthly_rent"] is None
    assert result["range"] is None
    assert result["comparables"] == []


def test_outlier_is_trimmed_when_enough_comparables_exist():
    rows = [_row(str(i), rent) for i, rent in enumerate([3800, 3850, 3900, 3950, 4000, 50_000])]
    result = estimate_rent(TARGET, rows, as_of="2026-09-01")

    assert result["sample_size"] == 5
    assert max(item["monthly_rent"] for item in result["comparables"]) < 50_000
    assert result["estimate_monthly_rent"] < 5000


def test_missing_comparable_attributes_reduce_confidence_and_widen_range():
    complete_rows = [_row(f"complete-{index}", 3900) for index in range(8)]
    sparse_rows = []
    for index in range(8):
        row = _row(f"sparse-{index}", 3900)
        for field in ("zip_code", "neighborhood", "bathrooms", "sqft", "year_built", "amenities"):
            row[field] = None
        sparse_rows.append(row)

    complete = estimate_rent(TARGET, complete_rows, as_of="2026-09-01")
    sparse = estimate_rent(TARGET, sparse_rows, as_of="2026-09-01")

    assert complete["confidence"]["score"] > sparse["confidence"]["score"]
    complete_width = complete["range"]["high"] - complete["range"]["low"]
    sparse_width = sparse["range"]["high"] - sparse["range"]["low"]
    assert complete_width < sparse_width


def test_request_normalizes_city_and_amenities_and_forbids_unknown_fields():
    request = RentEstimateRequest.model_validate(
        {
            "city": " san jose ",
            "bedrooms": 2,
            "property_type": "apartment",
            "amenities": ["Parking", " parking ", "In-Unit Laundry"],
        }
    )
    assert request.city == "San Jose"
    assert request.amenities == ["in-unit laundry", "parking"]


def test_db_adapter_reads_canonical_rental_observation_contract():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE rental_observations (
          observation_id TEXT, observed_on TEXT, city TEXT, zip_code TEXT,
          neighborhood TEXT, monthly_rent REAL, bedrooms INTEGER, bathrooms REAL,
          property_type TEXT, listing_status TEXT, sqft REAL, year_built INTEGER,
          amenities_json TEXT, source TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO rental_observations VALUES "
        "('r1','2026-01-02','San Jose','95125','Willow Glen',3800,2,2,"
        "'apartment','new',1000,2015,'[\"parking\"]','upload')"
    )

    rows = _load_observations(conn, None)
    assert rows[0]["amenities"] == ["parking"]
    assert rows[0]["monthly_rent"] == 3800
    assert "amenities_json" not in rows[0]


def test_estimate_endpoint_contract_uses_imported_observations():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE rental_observations (
          observation_id TEXT, observed_on TEXT, city TEXT, zip_code TEXT,
          neighborhood TEXT, monthly_rent REAL, bedrooms INTEGER, bathrooms REAL,
          property_type TEXT, listing_status TEXT, sqft REAL, year_built INTEGER,
          amenities_json TEXT, source TEXT
        )
        """
    )
    for index, rent in enumerate((3800, 3900, 4000)):
        conn.execute(
            "INSERT INTO rental_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"r{index}",
                "2026-06-01",
                "San Jose",
                "95125",
                "Willow Glen",
                rent,
                2,
                2,
                "apartment",
                "new",
                1000,
                2015,
                '["parking","in-unit laundry"]',
                "upload",
            ),
        )

    def connection_override():
        yield conn

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[db_conn] = connection_override
    app.dependency_overrides[ensure_local_request] = lambda: None
    response = TestClient(app).post(
        "/api/rentals/estimate",
        json={**TARGET, "as_of": "2026-09-01"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "estimated"
    assert body["estimate_monthly_rent"] == 3900
    assert body["sample_size"] == 3
    assert len(body["comparables"]) == 3
