"""Validated, provider-neutral rental observations."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TARGET_CITIES = ("San Jose", "Sunnyvale", "Mountain View", "Palo Alto")
PROPERTY_TYPES = ("apartment", "townhouse", "single_family")
LISTING_STATUSES = ("new", "existing")
AVAILABILITY_STATUSES = ("active", "inactive", "unknown")

_CITY_NAMES = {re.sub(r"[^a-z]", "", name.lower()): name for name in TARGET_CITIES}
_PROPERTY_NAMES = {
    "apartment": "apartment",
    "apt": "apartment",
    "townhouse": "townhouse",
    "townhome": "townhouse",
    "singlefamily": "single_family",
    "singlefamilyhome": "single_family",
    "sfh": "single_family",
}
_STATUS_NAMES = {
    "new": "new",
    "newrental": "new",
    "existing": "existing",
    "old": "existing",
    "existingrental": "existing",
}
_AVAILABILITY_NAMES = {value: value for value in AVAILABILITY_STATUSES}
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ZIP_PATTERN = re.compile(r"^\d{5}$")


def _three_year_cutoff(today: date) -> date:
    try:
        return today.replace(year=today.year - 3)
    except ValueError:  # February 29 becomes February 28 in a non-leap year.
        return today.replace(year=today.year - 3, day=28)


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z]", "", str(value).strip().lower())


def _clean_text(value: Any, *, field: str, max_length: int) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if len(text) > max_length or any(ord(char) < 32 for char in text):
        raise ValueError(f"{field} must be {max_length} printable characters or fewer")
    return text


class RentalObservation(BaseModel):
    """One asking-rent observation; unknown input columns are rejected."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    observation_id: str | None = None
    source: str = "local_upload"
    observed_on: date
    city: str
    zip_code: str | None = None
    neighborhood: str | None = None
    monthly_rent: float = Field(gt=0, le=100_000)
    bedrooms: int = Field(ge=1, le=3)
    bathrooms: float | None = Field(default=None, ge=0, le=20)
    property_type: str
    listing_status: str
    availability_status: str = "unknown"
    sqft: float | None = Field(default=None, ge=100, le=30_000)
    year_built: int | None = None
    amenities: list[str] = Field(default_factory=list, max_length=24)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    removed_on: date | None = None
    last_seen_on: date | None = None

    @field_validator("monthly_rent", "bedrooms", "bathrooms", "sqft", "year_built", mode="before")
    @classmethod
    def reject_boolean_numbers(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise TypeError("must be a number, not a boolean")
        return value

    @field_validator("observation_id")
    @classmethod
    def validate_observation_id(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not _ID_PATTERN.fullmatch(value):
            raise ValueError("must be 1-128 characters using letters, numbers, '.', '_', ':' or '-'")
        return value

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, value: Any) -> str:
        return _clean_text(value or "local_upload", field="source", max_length=100) or "local_upload"

    @field_validator("city", mode="before")
    @classmethod
    def validate_city(cls, value: Any) -> str:
        city = _CITY_NAMES.get(_normalized_key(value))
        if city is None:
            raise ValueError(f"must be one of: {', '.join(TARGET_CITIES)}")
        return city

    @field_validator("property_type", mode="before")
    @classmethod
    def validate_property_type(cls, value: Any) -> str:
        property_type = _PROPERTY_NAMES.get(_normalized_key(value))
        if property_type is None:
            raise ValueError(f"must be one of: {', '.join(PROPERTY_TYPES)}")
        return property_type

    @field_validator("listing_status", mode="before")
    @classmethod
    def validate_listing_status(cls, value: Any) -> str:
        listing_status = _STATUS_NAMES.get(_normalized_key(value))
        if listing_status is None:
            raise ValueError(f"must be one of: {', '.join(LISTING_STATUSES)}")
        return listing_status

    @field_validator("availability_status", mode="before")
    @classmethod
    def validate_availability_status(cls, value: Any) -> str:
        status = _AVAILABILITY_NAMES.get(_normalized_key(value or "unknown"))
        if status is None:
            raise ValueError(f"must be one of: {', '.join(AVAILABILITY_STATUSES)}")
        return status

    @field_validator("zip_code", mode="before")
    @classmethod
    def validate_zip_code(cls, value: Any) -> str | None:
        text = _clean_text(value, field="zip_code", max_length=5)
        if text is not None and not _ZIP_PATTERN.fullmatch(text):
            raise ValueError("must be a five-digit ZIP code")
        return text

    @field_validator("neighborhood", mode="before")
    @classmethod
    def validate_neighborhood(cls, value: Any) -> str | None:
        return _clean_text(value, field="neighborhood", max_length=100)

    @field_validator("year_built")
    @classmethod
    def validate_year_built(cls, value: int | None) -> int | None:
        current_year = datetime.now(UTC).year
        if value is not None and not 1800 <= value <= current_year + 1:
            raise ValueError(f"must be between 1800 and {current_year + 1}")
        return value

    @field_validator("amenities", mode="before")
    @classmethod
    def parse_amenities(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            value = [part for part in value.split("|") if part.strip()]
        if not isinstance(value, list):
            raise TypeError("must be an array or a pipe-separated string")
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError("amenity entries must be strings")
            text = _clean_text(item, field="amenity", max_length=48)
            if text:
                normalized = text.lower()
                if normalized not in cleaned:
                    cleaned.append(normalized)
        return cleaned

    @model_validator(mode="after")
    def validate_history_window(self) -> RentalObservation:
        today = datetime.now(UTC).date()
        if self.observed_on > today:
            raise ValueError("observed_on cannot be in the future")
        if self.observed_on < _three_year_cutoff(today):
            raise ValueError("observed_on must be within the last three years")
        if self.year_built is not None and self.year_built > self.observed_on.year + 1:
            raise ValueError("year_built cannot be after the observation year plus one")
        for field, value in (
            ("removed_on", self.removed_on),
            ("last_seen_on", self.last_seen_on),
        ):
            if value is not None and value > today:
                raise ValueError(f"{field} cannot be in the future")
            if value is not None and value < self.observed_on:
                raise ValueError(f"{field} cannot be before observed_on")
        return self
