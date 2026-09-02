"""Address lookup through the public Census Geocoder.

The geocoder is used only for search/centering. It is not a market-data source
and does not require a key. Provider credentials never enter this module.
"""

from __future__ import annotations

import httpx

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def geocode(query: str, *, timeout: float = 8.0) -> list[dict]:
    params = {
        "address": query,
        "benchmark": "Public_AR_Current",
        "format": "json",
    }
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(GEOCODER_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []

    matches = ((payload.get("result") or {}).get("addressMatches")) or []
    results: list[dict] = []
    for match in matches[:5]:
        coords = match.get("coordinates") or {}
        try:
            lon = float(coords["x"])
            lat = float(coords["y"])
        except (KeyError, TypeError, ValueError):
            continue
        results.append({"label": match.get("matchedAddress") or query, "lat": lat, "lon": lon})
    return results
