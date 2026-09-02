from __future__ import annotations

from fastapi import APIRouter, Depends

from realtykit.api.deps import ensure_store
from realtykit.api.schemas import GovernmentArea, GovernmentAreasResponse
from realtykit.freshness import build_freshness
from realtykit.store.db import connect
from realtykit.store.government import list_government_areas

router = APIRouter()


@router.get("/map/government-areas", response_model=GovernmentAreasResponse)
def government_areas(_ok: None = Depends(ensure_store)) -> GovernmentAreasResponse:
    conn = connect()
    try:
        rows = list_government_areas(conn)
    finally:
        conn.close()
    return GovernmentAreasResponse(
        freshness=build_freshness(prefer_source="government:santa_clara_parcels"),
        features=[GovernmentArea(**row) for row in rows],
        note=(
            "Official Santa Clara County city boundaries and address-derived parcel counts. "
            "The parcel feed does not contain sale prices."
        ),
    )
