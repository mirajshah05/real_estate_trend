from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from realtykit.api.deps import ensure_store
from realtykit.api.schemas import FreshnessResponse
from realtykit.freshness import build_freshness, honesty_banner

router = APIRouter()


def _payload() -> FreshnessResponse:
    block = build_freshness()
    return FreshnessResponse(
        freshness=block,
        goal={
            "max_age_days": 7,
            "honest_summary": honesty_banner(),
            "observation_sla_met": block.overall in {"live", "fresh"},
            "listing_sla_hours": 168,
            "note": "Monthly indexes and delayed public research files are shown with their real observation age.",
        },
    )


@router.get("/freshness", response_model=FreshnessResponse)
def freshness(_ok: None = Depends(ensure_store)) -> JSONResponse:
    body = _payload()
    return JSONResponse(
        content=body.model_dump(),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/meta/freshness", response_model=FreshnessResponse)
def freshness_alias() -> JSONResponse:
    return freshness()
