"""Bounded, atomic CSV/JSON imports for local rental research."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Any

from pydantic import ValidationError

from realtykit.models.rental import RentalObservation
from realtykit.store.rentals import (
    RentalIdentityConflict,
    prune_rental_observations,
    record_rental_import,
    upsert_rental_observations,
)

MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 25_000
MAX_REPORTED_ERRORS = 50

REQUIRED_FIELDS = {
    "observed_on",
    "city",
    "monthly_rent",
    "bedrooms",
    "property_type",
    "listing_status",
}
ALLOWED_FIELDS = set(RentalObservation.model_fields)
OPTIONAL_FIELDS = ALLOWED_FIELDS - REQUIRED_FIELDS


class RentalImportError(ValueError):
    def __init__(self, message: str, *, errors: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.errors = errors or []


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON number: {value}")


def _parse_json(content: str) -> list[Any]:
    try:
        payload = json.loads(content, parse_constant=_reject_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RentalImportError(f"Invalid JSON: {exc}") from None
    if isinstance(payload, dict):
        if set(payload) != {"observations"}:
            raise RentalImportError("JSON object must contain only an 'observations' array")
        payload = payload["observations"]
    if not isinstance(payload, list):
        raise RentalImportError("JSON content must be an array of observations")
    return payload


def _parse_csv(content: str) -> list[Any]:
    try:
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff"), newline=""))
        headers = reader.fieldnames
        if not headers:
            raise RentalImportError("CSV must have a header row")
        if len(headers) != len(set(headers)):
            raise RentalImportError("CSV headers must be unique")
        unknown = sorted(set(headers) - ALLOWED_FIELDS)
        missing = sorted(REQUIRED_FIELDS - set(headers))
        if unknown:
            raise RentalImportError(f"Unknown CSV columns: {', '.join(unknown)}")
        if missing:
            raise RentalImportError(f"Missing CSV columns: {', '.join(missing)}")
        rows = list(reader)
    except csv.Error as exc:
        raise RentalImportError(f"Invalid CSV: {exc}") from None
    if any(None in row for row in rows):
        raise RentalImportError("CSV rows cannot contain more values than the header")
    return rows


def _prepare_row(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError("each observation must be an object")
    data = dict(raw)
    for field in OPTIONAL_FIELDS:
        if data.get(field) == "":
            data[field] = None
    return data


def _stable_observation_id(row: RentalObservation) -> str:
    payload = row.model_dump(mode="json", exclude={"observation_id"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"local:{hashlib.sha256(encoded).hexdigest()[:32]}"


def parse_rental_import(content: str, file_format: str) -> list[RentalObservation]:
    """Parse and validate the full input before any database mutation occurs."""
    encoded = content.encode("utf-8")
    if not encoded:
        raise RentalImportError("Import content cannot be empty")
    if len(encoded) > MAX_IMPORT_BYTES:
        raise RentalImportError(f"Import exceeds the {MAX_IMPORT_BYTES}-byte limit")
    if "\x00" in content:
        raise RentalImportError("Import content cannot contain NUL bytes")

    raw_rows = _parse_csv(content) if file_format == "csv" else _parse_json(content)
    if not raw_rows:
        raise RentalImportError("Import must contain at least one observation")
    if len(raw_rows) > MAX_IMPORT_ROWS:
        raise RentalImportError(f"Import exceeds the {MAX_IMPORT_ROWS}-row limit")

    observations: list[RentalObservation] = []
    errors: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_rows, start=1):
        try:
            observation = RentalObservation.model_validate(_prepare_row(raw))
            if observation.observation_id is None:
                observation.observation_id = _stable_observation_id(observation)
            observations.append(observation)
        except (ValidationError, TypeError, ValueError) as exc:
            if len(errors) < MAX_REPORTED_ERRORS:
                detail = (
                    exc.errors(include_url=False, include_context=False, include_input=False)
                    if isinstance(exc, ValidationError)
                    else [{"msg": str(exc)}]
                )
                errors.append({"row": index, "errors": detail})
    if errors:
        raise RentalImportError(
            f"Import rejected: {len(errors)} row(s) shown with validation errors",
            errors=errors,
        )

    seen: set[str] = set()
    duplicate_ids = sorted(
        {
            str(row.observation_id)
            for row in observations
            if str(row.observation_id) in seen or seen.add(str(row.observation_id))
        }
    )
    if duplicate_ids:
        raise RentalImportError(
            "Import contains duplicate observation IDs",
            errors=[{"observation_id": value} for value in duplicate_ids[:MAX_REPORTED_ERRORS]],
        )
    return observations


def import_rentals(
    *,
    filename: str,
    file_format: str,
    content: str,
    conn,
) -> dict[str, Any]:
    """Validate and atomically persist one local rental-data upload."""
    if (
        not filename
        or len(filename) > 128
        or PurePath(filename).name != filename
        or "/" in filename
        or "\\" in filename
    ):
        raise RentalImportError("filename must be a basename of 1-128 characters")
    if any(ord(char) < 32 for char in filename):
        raise RentalImportError("filename must contain only printable characters")
    if file_format not in {"csv", "json"}:
        raise RentalImportError("format must be 'csv' or 'json'")
    if not filename.lower().endswith(f".{file_format}"):
        raise RentalImportError("filename extension must match format")

    observations = parse_rental_import(content, file_format)
    content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    import_id = f"rental:{content_sha256[:32]}"
    imported_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        with conn:
            today = datetime.now(UTC).date()
            try:
                cutoff = today.replace(year=today.year - 3)
            except ValueError:
                cutoff = today.replace(year=today.year - 3, day=28)
            prune_rental_observations(conn, before=cutoff)
            inserted, updated = upsert_rental_observations(
                observations,
                import_id=import_id,
                imported_at=imported_at,
                conn=conn,
            )
            record_rental_import(
                import_id=import_id,
                filename=filename,
                file_format=file_format,
                content_sha256=content_sha256,
                row_count=len(observations),
                inserted=inserted,
                updated=updated,
                imported_at=imported_at,
                conn=conn,
            )
    except RentalIdentityConflict as exc:
        raise RentalImportError(
            "Import would reuse an observation ID for a different event",
            errors=[{"observation_id": exc.observation_id, "message": str(exc)}],
        ) from None
    dates = [row.observed_on.isoformat() for row in observations]
    return {
        "import_id": import_id,
        "inserted": inserted,
        "updated": updated,
        "rejected": 0,
        "cities": sorted({row.city for row in observations}),
        "date_min": min(dates),
        "date_max": max(dates),
    }
