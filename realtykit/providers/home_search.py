"""Bounded home search. Cache only public property facts; discard owners/contacts."""

from datetime import timedelta
from math import asin, cos, isfinite, radians, sin, sqrt

from realtykit.log import utc_iso
from realtykit.providers import rentcast
from realtykit.store.provider_usage import get_cached, put_cached


def distance_miles(lat, lon, other_lat, other_lon):
    a, b = radians(other_lat - lat), radians(other_lon - lon)
    h = sin(a / 2) ** 2 + cos(radians(lat)) * cos(radians(other_lat)) * sin(b / 2) ** 2
    return 3958.8 * 2 * asin(sqrt(min(1, max(0, h))))


def _number(value):
    value = rentcast._number(value)
    return value if value is not None and isfinite(value) else None


def public_profile(item):
    lat, lon = _number(item.get("latitude")), _number(item.get("longitude"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return {
        "property_id": str(item.get("id") or ""),
        "address": item.get("formattedAddress") or item.get("addressLine1"),
        "city": item.get("city"),
        "state": item.get("state"),
        "zip_code": item.get("zipCode"),
        "lat": lat,
        "lon": lon,
        "property_type": item.get("propertyType"),
        "beds": _number(item.get("bedrooms")),
        "baths": _number(item.get("bathrooms")),
        "sqft": _number(item.get("squareFootage")),
    }


def _items(payload):
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError("Invalid provider payload")
    return payload


def subject(address, settings):
    key = rentcast._cache_key("home-subject", {"address": address.strip().lower()})
    cached = get_cached("rentcast", key, timedelta(days=1), settings)
    if cached is not None:
        return cached, True
    items = _items(
        rentcast._request(
            rentcast.PROPERTIES_URL, {"address": address, "limit": 2}, settings
        ).json()
    )
    profiles = [profile for item in items if (profile := public_profile(item))]
    put_cached("rentcast", key, profiles, settings)
    return profiles, False


def match_rows(items, criteria):
    rows = {}
    fetched = utc_iso()
    for item in items:
        profile = public_profile(item)
        if (
            not profile
            or not profile["property_id"]
            or profile["property_id"] == criteria.get("exclude_property_id")
        ):
            continue
        if str(item.get("status") or "").lower() != "active":
            continue
        distance = distance_miles(criteria["lat"], criteria["lon"], profile["lat"], profile["lon"])
        if distance > criteria["radius"]:
            continue
        wanted_type = criteria.get("property_type")
        if wanted_type and profile["property_type"] != wanted_type:
            continue
        price = _number(item.get("price"))
        values = {**profile, "price": price}
        ranges = [
            ("beds", "min_beds", "max_beds"),
            ("baths", "min_baths", "max_baths"),
            ("price", "min_price", "max_price"),
            ("sqft", "min_sqft", "max_sqft"),
        ]
        if any(
            (
                criteria.get(low) is not None
                and (values[field] is None or values[field] < criteria[low])
            )
            or (
                high
                and criteria.get(high) is not None
                and (values[field] is None or values[field] > criteria[high])
            )
            for field, low, high in ranges
        ):
            continue
        observed = rentcast._rental_date(item.get("lastSeenDate")) or rentcast._rental_date(
            item.get("listedDate")
        )
        if not observed:
            continue
        reasons = [f"{distance:.1f} miles from your search location"]
        if wanted_type:
            reasons.append(wanted_type)
        for lower, upper, label in [
            ("min_beds", "max_beds", "bedrooms"),
            ("min_baths", "max_baths", "bathrooms"),
        ]:
            if criteria.get(lower) is not None and criteria.get(lower) == criteria.get(upper):
                reasons.append(f"Exactly {criteria[lower]:g} {label}")
            else:
                if criteria.get(lower) is not None:
                    reasons.append(f"At least {criteria[lower]:g} {label}")
                if criteria.get(upper) is not None:
                    reasons.append(f"At most {criteria[upper]:g} {label}")
        for field, label in [
            ("max_price", "budget"),
            ("min_price", "price minimum"),
            ("min_sqft", "size minimum"),
            ("max_sqft", "size maximum"),
        ]:
            if criteria.get(field) is not None:
                reasons.append(f"Meets your {label}")
        identity = profile.pop("property_id")
        rows[identity] = {
            **profile,
            "listing_id": f"rentcast:{identity}",
            "provider": "rentcast",
            "price": price,
            "status": "active",
            "as_of": observed,
            "fetched_at": fetched,
            "distance_miles": round(distance, 2),
            "match_reasons": reasons,
            "intent": criteria["intent"],
        }
    return sorted(rows.values(), key=lambda row: (row["distance_miles"], row["listing_id"]))


def search(criteria, settings):
    key = rentcast._cache_key("home-matches-v2", criteria)
    cached = get_cached("rentcast", key, timedelta(hours=6), settings)
    if cached is not None:
        return cached[0], True
    params = {
        "latitude": criteria["lat"],
        "longitude": criteria["lon"],
        "radius": criteria["radius"],
        "status": "Active",
        "limit": 100,
    }
    if criteria.get("property_type"):
        params["propertyType"] = criteria["property_type"]
    for param, low, high in [
        ("bedrooms", "min_beds", "max_beds"),
        ("bathrooms", "min_baths", "max_baths"),
        ("price", "min_price", "max_price"),
        ("squareFootage", "min_sqft", "max_sqft"),
    ]:
        if criteria.get(low) is not None or (high and criteria.get(high) is not None):
            params[param] = (
                f"{criteria.get(low) if criteria.get(low) is not None else '*'}:{criteria.get(high) if high and criteria.get(high) is not None else '*'}"
            )
    url = rentcast.RENTAL_URL if criteria["intent"] == "rent" else rentcast.SALE_URL
    items = _items(rentcast._request(url, params, settings).json())
    result = {"listings": match_rows(items, criteria), "possibly_truncated": len(items) >= 100}
    put_cached("rentcast", key, [result], settings)
    return result, False
