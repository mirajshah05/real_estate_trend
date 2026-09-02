from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Listing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: str
    provider: str
    geo_id: str | None = None
    lat: float
    lon: float
    price: float | None = None
    beds: float | None = None
    baths: float | None = None
    sqft: float | None = None
    dom: int | None = None
    status: str = "active"
    listed_at: str | None = None
    as_of: str | None = None
    fetched_at: str | None = None
    outlier_score: float | None = None
    outlier_reasons: list[str] = Field(default_factory=list)


def validate_listing(payload: dict) -> Listing:
    """Require an observation clock before accepting a listing row."""
    as_of = payload.get("listed_at") or payload.get("as_of") or payload.get("observation_as_of")
    if not as_of:
        raise ValueError("as_of is required")
    data = {
        "listing_id": payload.get("listing_id") or "unknown",
        "provider": payload.get("provider") or payload.get("source") or "unknown",
        "geo_id": payload.get("geo_id"),
        "lat": float(payload.get("lat") if payload.get("lat") is not None else 0.0),
        "lon": float(payload.get("lon") if payload.get("lon") is not None else 0.0),
        "price": payload.get("price"),
        "dom": payload.get("dom"),
        "status": payload.get("status") or "active",
        "listed_at": as_of,
    }
    return Listing.model_validate(data)
