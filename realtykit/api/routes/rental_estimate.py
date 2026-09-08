from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from realtykit.analysis.rent_estimator import estimate_rent
from realtykit.api.deps import db_conn, ensure_local_request

router = APIRouter()

BayAreaCity = Literal["San Jose", "Sunnyvale", "Mountain View", "Palo Alto"]
PropertyType = Literal["apartment", "townhouse", "single_family"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RentEstimateRequest(_StrictModel):
    city: BayAreaCity
    neighborhood: str | None = Field(default=None, max_length=120)
    zip_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    bedrooms: int = Field(ge=1, le=3)
    bathrooms: float | None = Field(default=None, ge=0.5, le=10)
    property_type: PropertyType
    sqft: float | None = Field(default=None, ge=100, le=20_000)
    year_built: int | None = Field(default=None, ge=1800, le=2100)
    amenities: list[str] = Field(default_factory=list, max_length=30)
    as_of: date | None = None

    @field_validator("city", mode="before")
    @classmethod
    def normalize_city(cls, value: object) -> object:
        if isinstance(value, str):
            canonical = {
                "san jose": "San Jose",
                "sunnyvale": "Sunnyvale",
                "mountain view": "Mountain View",
                "palo alto": "Palo Alto",
            }
            return canonical.get(" ".join(value.strip().lower().split()), value)
        return value

    @field_validator("amenities")
    @classmethod
    def normalize_amenities(cls, value: list[str]) -> list[str]:
        cleaned = {" ".join(item.strip().lower().split()) for item in value if item.strip()}
        return sorted(cleaned)


class RentRange(_StrictModel):
    low: float
    high: float


class RentConfidence(_StrictModel):
    score: float = Field(ge=0, le=1)
    label: Literal["none", "low", "medium", "high"]


class RentAdjustment(_StrictModel):
    factor: str
    impact_dollars: float
    description: str


class RentComparable(_StrictModel):
    observation_id: str
    observed_on: str
    city: str
    neighborhood: str | None = None
    monthly_rent: float
    adjusted_rent: float
    similarity: float = Field(ge=0, le=1)
    bedrooms: int
    bathrooms: float | None = None
    property_type: PropertyType
    sqft: float | None = None
    year_built: int | None = None
    matched_amenities: list[str] = Field(default_factory=list)


class RentEstimateResponse(_StrictModel):
    status: Literal["estimated", "low_data", "no_data"]
    method: Literal["comparable_adjustment_v1"]
    as_of: str
    estimate_monthly_rent: float | None = None
    range: RentRange | None = None
    confidence: RentConfidence
    sample_size: int
    comparable_pool_size: int
    adjustments: list[RentAdjustment] = Field(default_factory=list)
    comparables: list[RentComparable] = Field(default_factory=list)
    disclaimer: str


def _load_observations(conn: sqlite3.Connection, as_of: date | None) -> list[dict]:
    """Read the canonical import table; tolerate deployments before its migration."""

    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'rental_observations'"
    ).fetchone()
    if not table:
        return []
    params: tuple[str, ...] = ()
    where = ""
    if as_of is not None:
        where = " WHERE observed_on <= ?"
        params = (as_of.isoformat(),)
    rows = conn.execute(
        """
        SELECT observation_id, observed_on, city, zip_code, neighborhood, monthly_rent,
               bedrooms, bathrooms, property_type, listing_status, sqft, year_built,
               amenities_json, source
          FROM rental_observations
        """
        + where,
        params,
    ).fetchall()
    observations = []
    for source_row in rows:
        row = dict(source_row)
        try:
            row["amenities"] = json.loads(row.pop("amenities_json") or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            row["amenities"] = []
        observations.append(row)
    return observations


@router.post("/rentals/estimate", response_model=RentEstimateResponse)
def rental_estimate(
    body: RentEstimateRequest,
    _local: None = Depends(ensure_local_request),
    conn: sqlite3.Connection = Depends(db_conn),  # noqa: B008
) -> RentEstimateResponse:
    observations = _load_observations(conn, body.as_of)
    result = estimate_rent(
        body.model_dump(exclude={"as_of"}),
        observations,
        as_of=body.as_of,
    )
    return RentEstimateResponse.model_validate(result)
