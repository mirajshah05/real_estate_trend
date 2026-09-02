"""RentCast listings and sold-property records. Credentials stay server-side."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import httpx

from realtykit.log import utc_iso
from realtykit.providers.base import FetchOutcome
from realtykit.settings import Settings, get_settings
from realtykit.store.provider_usage import get_cached, put_cached, record_attempt, record_result
from realtykit.store.sources import upsert_source

SALE_URL = "https://api.rentcast.io/v1/listings/sale"
PROPERTIES_URL = "https://api.rentcast.io/v1/properties"


def _validate_bbox(west: float, south: float, east: float, north: float) -> None:
    if not (
        -180 <= west < east <= 180
        and -90 <= south < north <= 90
        and east - west <= 2.5
        and north - south <= 2.5
    ):
        raise ValueError("listing bbox must be valid and no larger than 2.5 degrees")


def _number(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _cache_key(kind: str, values: dict) -> str:
    stable = json.dumps({"kind": kind, **values}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _request(url: str, params: dict, settings: Settings) -> httpx.Response:
    record_attempt("rentcast", settings)
    headers = {
        "X-Api-Key": settings.rentcast_api_key or "",
        "Accept": "application/json",
        "User-Agent": settings.user_agent,
    }
    response: httpx.Response | None = None
    try:
        with httpx.Client(timeout=20.0, headers=headers) as client:
            response = client.get(url, params=params)
        record_result(
            "rentcast", response.status_code, successful=response.is_success, settings=settings
        )
        response.raise_for_status()
        return response
    except Exception:
        if response is None:
            record_result("rentcast", None, successful=False, settings=settings)
        raise


def ingest(conn: sqlite3.Connection, settings: Settings | None = None, **_kwargs) -> FetchOutcome:
    settings = settings or get_settings()
    if not settings.has_rentcast_key:
        out = FetchOutcome(
            source_id="rentcast:listings",
            provider="rentcast",
            dataset="listings_and_property_sales",
            url=SALE_URL,
            status="skipped",
            fetched_at=utc_iso(),
            cadence="daily",
            freshness="unavailable",
            note="Skipped — RENTCAST_API_KEY not set.",
        )
        upsert_source(out.as_source_row(), conn)
        return out

    out = FetchOutcome(
        source_id="rentcast:listings",
        provider="rentcast",
        dataset="listings_and_property_sales",
        url=SALE_URL,
        status="ok",
        fetched_at=utc_iso(),
        cadence="daily",
        freshness="fresh",
        note="Key present. Sanitized listing and sale records are fetched on demand and cached locally.",
    )
    upsert_source(out.as_source_row(), conn)
    return out


def _search_geometry(
    west: float, south: float, east: float, north: float
) -> tuple[float, float, float]:
    lat = (south + north) / 2
    lon = (west + east) / 2
    span = max(east - west, north - south)
    return lat, lon, min(100.0, max(1.0, span * 69.0))


def fetch_bbox(
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    limit: int = 200,
    settings: Settings | None = None,
) -> tuple[list[dict], bool]:
    settings = settings or get_settings()
    if not settings.has_rentcast_key:
        return [], False
    _validate_bbox(west, south, east, north)
    lat, lon, radius = _search_geometry(west, south, east, north)
    cache_key = _cache_key(
        "active-listings",
        {
            "bbox": [round(west, 3), round(south, 3), round(east, 3), round(north, 3)],
            "limit": limit,
        },
    )
    cached = get_cached("rentcast", cache_key, timedelta(hours=6), settings)
    if cached is not None:
        return cached, True

    payload = _request(
        SALE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "radius": radius,
            "status": "Active",
            "limit": min(limit, 500),
        },
        settings,
    ).json()
    rows = payload if isinstance(payload, list) else payload.get("listings") or []
    listings = []
    fetched = utc_iso()
    for i, item in enumerate(rows):
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
                "address": item.get("formattedAddress"),
                "city": item.get("city"),
                "state": item.get("state"),
                "zip_code": item.get("zipCode"),
                "property_type": item.get("propertyType"),
                "lat": float(plat),
                "lon": float(plon),
                "price": _number(item.get("price")),
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
    put_cached("rentcast", cache_key, listings, settings)
    return listings, False


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value[:10] if len(value) >= 10 else None


def fetch_sold_bbox(
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    lookback_days: int = 365,
    limit: int = 200,
    settings: Settings | None = None,
) -> tuple[list[dict], bool]:
    """Return sanitized sale events; owner and assessment fields are discarded."""
    settings = settings or get_settings()
    if not settings.has_rentcast_key:
        return [], False
    _validate_bbox(west, south, east, north)
    lat, lon, radius = _search_geometry(west, south, east, north)
    cache_key = _cache_key(
        "recorded-sales",
        {
            "bbox": [round(west, 3), round(south, 3), round(east, 3), round(north, 3)],
            "days": lookback_days,
            "limit": limit,
        },
    )
    cached = get_cached("rentcast", cache_key, timedelta(hours=24), settings)
    if cached is not None:
        return cached, True

    payload = _request(
        PROPERTIES_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "radius": radius,
            "saleDateRange": lookback_days,
            "limit": min(limit, 500),
        },
        settings,
    ).json()
    properties = payload if isinstance(payload, list) else payload.get("properties") or []
    cutoff = (datetime.now(UTC) - timedelta(days=lookback_days)).date().isoformat()
    fetched = utc_iso()
    sales: list[dict] = []
    seen: set[str] = set()
    for i, item in enumerate(properties):
        plat = _number(item.get("latitude"))
        plon = _number(item.get("longitude"))
        if plat is None or plon is None or not (south <= plat <= north and west <= plon <= east):
            continue
        property_id = str(item.get("id") or i)
        history = item.get("history") if isinstance(item.get("history"), dict) else {}
        events = list(history.values())
        if not events and item.get("lastSaleDate"):
            events = [
                {
                    "event": "Sale",
                    "date": item.get("lastSaleDate"),
                    "price": item.get("lastSalePrice"),
                }
            ]
        for event in events:
            if not isinstance(event, dict) or str(event.get("event", "")).lower() != "sale":
                continue
            sale_date = _iso_date(event.get("date"))
            if not sale_date or sale_date < cutoff:
                continue
            price = _number(event.get("price"))
            event_seed = f"{property_id}|{sale_date}|{price}"
            event_id = f"rentcast:{hashlib.sha256(event_seed.encode()).hexdigest()[:24]}"
            if event_id in seen:
                continue
            seen.add(event_id)
            sales.append(
                {
                    "event_id": event_id,
                    "provider": "rentcast",
                    "property_id": property_id,
                    "address": item.get("formattedAddress"),
                    "city": item.get("city"),
                    "state": item.get("state"),
                    "zip_code": item.get("zipCode"),
                    "lat": float(plat),
                    "lon": float(plon),
                    "sale_date": sale_date,
                    "price": price,
                    "property_type": item.get("propertyType"),
                    "beds": _number(item.get("bedrooms")),
                    "baths": _number(item.get("bathrooms")),
                    "sqft": _number(item.get("squareFootage")),
                    "fetched_at": fetched,
                }
            )
    sales.sort(key=lambda row: row["sale_date"], reverse=True)
    put_cached("rentcast", cache_key, sales, settings)
    return sales, False
