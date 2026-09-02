from __future__ import annotations

from datetime import UTC, datetime

import pytest

from realtykit.providers.california_gis import _center, _freshness, _observation_date


def test_geometry_center_uses_boundary_extent():
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-122.2, 37.2], [-121.8, 37.2], [-121.8, 37.6], [-122.2, 37.6]]],
    }
    assert _center(geometry) == pytest.approx((37.4, -122.0))


def test_arcgis_last_edit_date_becomes_utc_date():
    timestamp = datetime(2026, 8, 29, 12, tzinfo=UTC).timestamp() * 1000
    assert _observation_date({"editingInfo": {"lastEditDate": timestamp}}) == "2026-08-29"


def test_missing_observation_is_not_painted_fresh():
    assert _freshness(None) == "unavailable"
