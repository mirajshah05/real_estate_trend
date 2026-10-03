"""Explicit, local-only provider searches with the shared monthly request budget."""

from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from realtykit.api.deps import ensure_local_request, ensure_store
from realtykit.providers import home_search
from realtykit.settings import get_settings
from realtykit.store.provider_usage import ProviderQuotaExceeded, usage_snapshot

router = APIRouter(dependencies=[Depends(ensure_local_request), Depends(ensure_store)])


class SubjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    address: str = Field(min_length=8, max_length=250)


class HomeSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    intent: Literal["buy", "rent"] = "buy"
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius: float = Field(default=5, ge=0.1, le=25)
    property_type: (
        Literal[
            "Single Family",
            "Condo",
            "Townhouse",
            "Manufactured",
            "Multi-Family",
            "Apartment",
            "Land",
        ]
        | None
    ) = None
    min_beds: float | None = Field(default=None, ge=0, le=20)
    max_beds: float | None = Field(default=None, ge=0, le=20)
    min_baths: float | None = Field(default=None, ge=0, le=20)
    max_baths: float | None = Field(default=None, ge=0, le=20)
    min_price: float | None = Field(default=None, ge=0, le=100_000_000)
    max_price: float | None = Field(default=None, gt=0, le=100_000_000)
    min_sqft: float | None = Field(default=None, ge=0, le=100_000)
    max_sqft: float | None = Field(default=None, gt=0, le=100_000)
    exclude_property_id: str | None = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def ordered_ranges(self):
        for low, high in [
            (self.min_price, self.max_price),
            (self.min_sqft, self.max_sqft),
            (self.min_beds, self.max_beds),
            (self.min_baths, self.max_baths),
        ]:
            if low is not None and high is not None and low > high:
                raise ValueError("Minimum must not exceed maximum")
        return self


def configured_settings():
    settings = get_settings()
    if not settings.has_rentcast_key:
        raise HTTPException(
            503,
            detail={
                "code": "provider_key_missing",
                "message": "Home search needs RENTCAST_API_KEY in the local backend configuration.",
            },
        )
    return settings


def provider_call(fn):
    try:
        return fn()
    except ProviderQuotaExceeded as exc:
        raise HTTPException(
            429, detail={"code": "provider_quota_reached", "message": str(exc)}
        ) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        message = (
            "RentCast denied this request. Check the API key and plan access in your RentCast dashboard."
            if status in {401, 403}
            else "RentCast could not complete this search. Try again later."
        )
        raise HTTPException(
            502, detail={"code": "provider_unavailable", "message": message}
        ) from exc
    except (httpx.RequestError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(
            502,
            detail={
                "code": "provider_unavailable",
                "message": "Home search could not reach or read RentCast. Try again later.",
            },
        ) from exc


@router.get("/homes/status")
def status():
    settings = get_settings()
    return {"configured": settings.has_rentcast_key, "usage": usage_snapshot("rentcast", settings)}


@router.post("/homes/subject")
def subject(body: SubjectRequest):
    settings = configured_settings()
    profiles, cached = provider_call(lambda: home_search.subject(body.address, settings))
    if not profiles:
        raise HTTPException(
            404,
            detail={
                "code": "address_not_found",
                "message": "No property record found. Include street, city, state, ZIP and unit, or search by requirements instead.",
            },
        )
    if len(profiles) > 1:
        raise HTTPException(
            409,
            detail={
                "code": "address_ambiguous",
                "message": "More than one property matched. Add the ZIP and unit number, or search by requirements.",
            },
        )
    return {
        "property": profiles[0],
        "cached": cached,
        "usage": usage_snapshot("rentcast", settings),
    }


@router.post("/homes/search")
def search(body: HomeSearchRequest):
    settings = configured_settings()
    result, cached = provider_call(lambda: home_search.search(body.model_dump(), settings))
    return {
        **result,
        "cached": cached,
        "usage": usage_snapshot("rentcast", settings),
        "note": "Active asking prices, not closed-sale prices. RentCast supplies up to 100 records ordered by its latest observation date; we enforce your filters and default to distance sorting within that sample. Coverage is not exhaustive. Cached for six hours.",
    }
