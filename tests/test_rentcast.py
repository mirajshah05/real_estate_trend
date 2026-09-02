from __future__ import annotations

from pathlib import Path

from realtykit.providers import rentcast
from realtykit.settings import Settings


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def _settings(path: Path) -> Settings:
    return Settings(_env_file=None, REALTYKIT_DATA_DIR=path, RENTCAST_API_KEY="test-only")


def test_sale_history_discards_owner_and_assessment_data(monkeypatch, tmp_path: Path):
    payload = [
        {
            "id": "property-1",
            "formattedAddress": "100 Test Ave, Sunnyvale, CA 94086",
            "city": "Sunnyvale",
            "state": "CA",
            "zipCode": "94086",
            "latitude": 37.38,
            "longitude": -122.02,
            "propertyType": "Single Family",
            "bedrooms": 3,
            "bathrooms": 2,
            "squareFootage": 1500,
            "owner": {"names": ["must not persist"]},
            "taxAssessments": {"2025": {"value": 999999}},
            "history": {
                "2026-07-01": {
                    "event": "Sale",
                    "date": "2026-07-01T00:00:00.000Z",
                    "price": 1800000,
                }
            },
        }
    ]
    monkeypatch.setattr(rentcast, "get_cached", lambda *_args, **_kwargs: None)
    cached_payload = {}
    monkeypatch.setattr(
        rentcast, "put_cached", lambda _p, _k, rows, _s: cached_payload.setdefault("rows", rows)
    )
    monkeypatch.setattr(rentcast, "_request", lambda *_args, **_kwargs: FakeResponse(payload))

    rows, cached = rentcast.fetch_sold_bbox(
        west=-122.1,
        south=37.3,
        east=-121.9,
        north=37.5,
        lookback_days=365,
        settings=_settings(tmp_path),
    )
    assert cached is False
    assert rows[0]["price"] == 1800000
    assert rows[0]["sale_date"] == "2026-07-01"
    assert "owner" not in rows[0]
    assert "taxAssessments" not in rows[0]
    assert cached_payload["rows"] == rows
