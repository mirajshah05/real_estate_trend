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
RENTAL_URL = "https://api.rentcast.io/v1/listings/rental/long-term"
PROPERTIES_URL = "https://api.rentcast.io/v1/properties"
TARGET_RENTAL_CITIES = ("San Jose", "Sunnyvale", "Mountain View", "Palo Alto")
_RENTAL_PROPERTY_TYPES = {
    "apartment": "apartment",
    "townhouse": "townhouse",
    "single family": "single_family",
}


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
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return None


def _rental_date(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return None


def _rental_cutoff(today) -> str:
    try:
        return today.replace(year=today.year - 3).isoformat()
    except ValueError:
        return today.replace(year=today.year - 3, day=28).isoformat()


def _canonical_rental_rows(items: list[dict], *, city: str, status: str) -> list[dict]:
    """Discard contacts/MLS metadata and expand lawful rental history events."""
    today = datetime.now(UTC).date()
    cutoff = _rental_cutoff(today)
    rows: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("city") or "").strip().lower() != city.lower():
            continue
        if str(item.get("state") or "").upper() != "CA":
            continue
        property_type = _RENTAL_PROPERTY_TYPES.get(
            str(item.get("propertyType") or "").strip().lower()
        )
        bedrooms = _number(item.get("bedrooms"))
        if property_type is None or bedrooms is None or not bedrooms.is_integer():
            continue
        bedroom_count = int(bedrooms)
        if bedroom_count not in {1, 2, 3}:
            continue
        property_id = str(item.get("id") or "").strip()
        if not property_id:
            continue

        events: list[dict] = []
        history = item.get("history")
        if isinstance(history, dict):
            for event in history.values():
                if not isinstance(event, dict):
                    continue
                if str(event.get("event") or "").strip().lower() != "rental listing":
                    continue
                events.append(
                    {
                        **event,
                        "availability": "inactive" if event.get("removedDate") else "unknown",
                    }
                )
        events.append(
            {
                "price": item.get("price"),
                "listedDate": item.get("listedDate"),
                "removedDate": item.get("removedDate"),
                "daysOnMarket": item.get("daysOnMarket"),
                "lastSeenDate": item.get("lastSeenDate"),
                "availability": status,
            }
        )

        for event in events:
            observed_on = _rental_date(event.get("listedDate"))
            price = _number(event.get("price"))
            if (
                observed_on is None
                or observed_on < cutoff
                or observed_on > today.isoformat()
                or price is None
                or not 0 < price <= 100_000
            ):
                continue
            event_seed = f"{property_id}|{observed_on}"
            observation_id = f"rentcast:{hashlib.sha256(event_seed.encode()).hexdigest()[:32]}"
            days_on_market = _number(event.get("daysOnMarket"))
            if days_on_market is None:
                days_on_market = (today - datetime.fromisoformat(observed_on).date()).days
            baths = _number(item.get("bathrooms"))
            sqft = _number(item.get("squareFootage"))
            year_built = _number(item.get("yearBuilt"))
            latitude = _number(item.get("latitude"))
            longitude = _number(item.get("longitude"))
            zip_code = str(item.get("zipCode") or "").strip()
            removed_on = _rental_date(event.get("removedDate"))
            last_seen_on = _rental_date(event.get("lastSeenDate"))
            if removed_on and (removed_on < observed_on or removed_on > today.isoformat()):
                removed_on = None
            if last_seen_on and (last_seen_on < observed_on or last_seen_on > today.isoformat()):
                last_seen_on = None
            rows[observation_id] = {
                "observation_id": observation_id,
                "source": "rentcast_api",
                "observed_on": observed_on,
                "city": city,
                "zip_code": zip_code if len(zip_code) == 5 and zip_code.isdigit() else None,
                "monthly_rent": price,
                "bedrooms": bedroom_count,
                "bathrooms": baths if baths is not None and 0 <= baths <= 20 else None,
                "property_type": property_type,
                "listing_status": "new" if days_on_market <= 30 else "existing",
                "availability_status": event.get("availability") or "unknown",
                "sqft": sqft if sqft is not None and 100 <= sqft <= 30_000 else None,
                "year_built": int(year_built)
                if year_built is not None
                and year_built.is_integer()
                and 1800 <= year_built <= today.year + 1
                else None,
                "amenities": [],
                "latitude": latitude if latitude is not None and -90 <= latitude <= 90 else None,
                "longitude": longitude
                if longitude is not None and -180 <= longitude <= 180
                else None,
                "removed_on": removed_on,
                "last_seen_on": last_seen_on,
            }
    return sorted(rows.values(), key=lambda row: (row["observed_on"], row["observation_id"]))


def fetch_city_rentals(
    *,
    city: str,
    status: str,
    days_old: int = 1095,
    limit: int = 100,
    settings: Settings | None = None,
    force: bool = False,
) -> tuple[list[dict], bool]:
    """Fetch one bounded page of sanitized long-term rental listings."""
    settings = settings or get_settings()
    if not settings.has_rentcast_key:
        return [], False
    if city not in TARGET_RENTAL_CITIES:
        raise ValueError("city is outside the four-city rental collection scope")
    normalized_status = status.strip().lower()
    if normalized_status not in {"active", "inactive"}:
        raise ValueError("status must be active or inactive")
    if not 1 <= days_old <= 1095 or not 1 <= limit <= 500:
        raise ValueError("days_old must be 1-1095 and limit must be 1-500")
    cache_key = _cache_key(
        "city-rentals",
        {"city": city, "status": normalized_status, "days_old": days_old, "limit": limit},
    )
    cached = None if force else get_cached("rentcast", cache_key, timedelta(hours=24), settings)
    if cached is not None:
        return cached, True
    payload = _request(
        RENTAL_URL,
        {
            "city": city,
            "state": "CA",
            "status": normalized_status.title(),
            "bedrooms": "1:3",
            "propertyType": "Apartment|Townhouse|Single Family",
            "daysOld": f"*:{days_old}",
            "limit": limit,
            "offset": 0,
        },
        settings,
    ).json()
    items = payload if isinstance(payload, list) else []
    rows = _canonical_rental_rows(items, city=city, status=normalized_status)
    put_cached("rentcast", cache_key, rows, settings)
    return rows, False


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
        "recorded-sales-v3",
        {
            "bbox": [west, south, east, north],
            "search_day": datetime.now(UTC).date().isoformat(),
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
        events = [
            {**event, "record_origin": "sale_history"}
            for event in history.values()
            if isinstance(event, dict)
        ]
        last_sale_date = _iso_date(item.get("lastSaleDate"))
        if last_sale_date and not any(
            isinstance(event, dict)
            and str(event.get("event", "")).lower() == "sale"
            and _iso_date(event.get("date")) == last_sale_date
            for event in events
        ):
            events.extend(
                [
                    {
                        "event": "Sale",
                        "date": item.get("lastSaleDate"),
                        "price": item.get("lastSalePrice"),
                        "record_origin": "last_sale_fields",
                    }
                ]
            )
        for event in events:
            if not isinstance(event, dict) or str(event.get("event", "")).lower() != "sale":
                continue
            sale_date = _iso_date(event.get("date"))
            if (
                not sale_date
                or sale_date < cutoff
                or sale_date > datetime.now(UTC).date().isoformat()
            ):
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
                    "record_origin": event["record_origin"],
                }
            )
    sales.sort(key=lambda row: row["sale_date"], reverse=True)
    put_cached("rentcast", cache_key, sales, settings)
    return sales, False
