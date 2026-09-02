"""RentCast listings. Skip unless RENTCAST_API_KEY is set. Key from env only."""

from __future__ import annotations

import sqlite3

import httpx

from realtykit.log import utc_iso
from realtykit.providers.base import FetchOutcome
from realtykit.settings import Settings, get_settings
from realtykit.store.sources import upsert_source

SALE_URL = "https://api.rentcast.io/v1/listings/sale"


def _validate_bbox(west: float, south: float, east: float, north: float) -> None:
    if not (
        -180 <= west < east <= 180
        and -90 <= south < north <= 90
        and east - west <= 1
        and north - south <= 1
    ):
        raise ValueError("listing bbox must be valid and no larger than 1 degree")


def _number(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def ingest(conn: sqlite3.Connection, settings: Settings | None = None, **_kwargs) -> FetchOutcome:
    settings = settings or get_settings()
    if not settings.has_rentcast_key:
        out = FetchOutcome(
            source_id="rentcast:listings",
            provider="rentcast",
            dataset="listings_sale",
            url=SALE_URL,
            status="skipped",
            fetched_at=utc_iso(),
            cadence="daily",
            freshness="unavailable",
            note="Skipped — RENTCAST_API_KEY not set. Metro outliers only; empty pin layer.",
        )
        upsert_source(out.as_source_row(), conn)
        return out

    # Viewport pulls happen on /api/map/listings; ingest only records that a key exists.
    out = FetchOutcome(
        source_id="rentcast:listings",
        provider="rentcast",
        dataset="listings_sale",
        url=SALE_URL,
        status="ok",
        fetched_at=utc_iso(),
        cadence="daily",
        freshness="fresh",
        note="Key present. Listings fetched on demand per bbox, not nationwide.",
    )
    upsert_source(out.as_source_row(), conn)
    return out


def fetch_bbox(
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    limit: int = 200,
    settings: Settings | None = None,
) -> list[dict]:
    settings = settings or get_settings()
    if not settings.has_rentcast_key:
        return []
    _validate_bbox(west, south, east, north)
    lat = (south + north) / 2
    lon = (west + east) / 2
    # radius miles from bbox span, capped at 100
    span = max(east - west, north - south)
    radius = min(100.0, max(1.0, span * 69.0))
    headers = {
        "X-Api-Key": settings.rentcast_api_key or "",
        "Accept": "application/json",
        "User-Agent": settings.user_agent,
    }
    params = {"latitude": lat, "longitude": lon, "radius": radius, "status": "Active", "limit": min(limit, 500)}
    with httpx.Client(timeout=20.0, headers=headers) as client:
        resp = client.get(SALE_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()
    rows = payload if isinstance(payload, list) else payload.get("listings") or []
    listings = []
    fetched = utc_iso()
    for i, item in enumerate(rows):
        price = _number(item.get("price"))
        plat = _number(item.get("latitude"))
        plon = _number(item.get("longitude"))
        if plat is None or plon is None or not (south <= plat <= north and west <= plon <= east):
            continue
        listed_at = item.get("listedDate")
        as_of = item.get("lastSeenDate") or listed_at
        if not as_of:
            continue
        listings.append(
            {
                "listing_id": f"rentcast:{item.get('id') or i}",
                "provider": "rentcast",
                "lat": float(plat),
                "lon": float(plon),
                "price": price,
                "beds": _number(item.get("bedrooms")),
                "baths": _number(item.get("bathrooms")),
                "sqft": _number(item.get("squareFootage")),
                "dom": _number(item.get("daysOnMarket")),
                "status": (item.get("status") or "active").lower(),
                "listed_at": listed_at,
                "as_of": as_of,
                "fetched_at": fetched,
            }
        )
    return listings
