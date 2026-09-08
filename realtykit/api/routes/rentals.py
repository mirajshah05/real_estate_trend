"""Local rental-history imports and segmented trend queries."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from realtykit.api.deps import db_conn, ensure_local_request
from realtykit.api.schemas import (
    RentalImportBody,
    RentalImportResponse,
    RentalObservationsResponse,
    RentalTrendsResponse,
)
from realtykit.ingest.rentals import RentalImportError, import_rentals
from realtykit.store.provider_usage import usage_snapshot
from realtykit.store.rentals import list_rental_observations, rental_trends

router = APIRouter()

City = Literal["San Jose", "Sunnyvale", "Mountain View", "Palo Alto"]
PropertyType = Literal["apartment", "townhouse", "single_family"]
ListingStatus = Literal["new", "existing"]
AvailabilityStatus = Literal["active", "inactive", "unknown"]
LocalRequest = Annotated[None, Depends(ensure_local_request)]
DatabaseConnection = Annotated[sqlite3.Connection, Depends(db_conn)]


@router.post("/rentals/import", response_model=RentalImportResponse)
def rental_import(
    body: RentalImportBody,
    _local: LocalRequest,
    conn: DatabaseConnection,
) -> RentalImportResponse | JSONResponse:
    try:
        result = import_rentals(
            filename=body.filename,
            file_format=body.format,
            content=body.content,
            conn=conn,
        )
    except RentalImportError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_rental_import",
                    "message": str(exc),
                    "details": exc.errors,
                }
            },
            headers={"Cache-Control": "no-store"},
        )
    return RentalImportResponse(**result)


@router.get("/rentals/trends", response_model=RentalTrendsResponse)
def get_rental_trends(
    city: Annotated[City, Query()],
    _local: LocalRequest,
    conn: DatabaseConnection,
    months: Annotated[int, Query(ge=1, le=36)] = 12,
    as_of: Annotated[date | None, Query()] = None,
    bedrooms: Annotated[int | None, Query(ge=1, le=3)] = None,
    property_type: Annotated[PropertyType | None, Query()] = None,
    listing_status: Annotated[ListingStatus | None, Query()] = None,
    availability_status: Annotated[AvailabilityStatus | None, Query()] = None,
) -> RentalTrendsResponse:
    if as_of is not None and as_of > datetime.now(UTC).date():
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_as_of",
                "message": "as_of cannot be in the future",
            },
        )
    result = rental_trends(
        conn,
        city=city,
        months=months,
        as_of=as_of,
        bedrooms=bedrooms,
        property_type=property_type,
        listing_status=listing_status,
        availability_status=availability_status,
    )
    result["rentcast_usage"] = usage_snapshot("rentcast")
    return RentalTrendsResponse(**result)


@router.get("/rentals/observations", response_model=RentalObservationsResponse)
def get_rental_observations(
    _local: LocalRequest,
    conn: DatabaseConnection,
    city: Annotated[City | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RentalObservationsResponse:
    observations, total = list_rental_observations(
        conn, city=city, limit=limit, offset=offset
    )
    return RentalObservationsResponse(
        total=total,
        limit=limit,
        offset=offset,
        observations=observations,
    )
