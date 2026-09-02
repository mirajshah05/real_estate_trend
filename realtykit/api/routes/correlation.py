from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from realtykit.analysis.constants import DEFAULT_WINDOW_WEEKS, DISCLAIMER
from realtykit.analysis.correlation import pearson_pairs
from realtykit.api.deps import ensure_store, geo_param
from realtykit.api.schemas import CorrelationResponse
from realtykit.freshness import build_freshness
from realtykit.store.facts import macro_series, series_for

router = APIRouter()


@router.get("/correlation", response_model=CorrelationResponse)
def correlation(
    geo_id: str = Depends(geo_param),
    housing: str = Query(default="inventory"),
    window_weeks: int = Query(default=DEFAULT_WINDOW_WEEKS, ge=26, le=260),
    _ok: None = Depends(ensure_store),
) -> CorrelationResponse:
    housing_pts = series_for(
        geo_id,
        housing,
        limit=window_weeks + 4,
        provider="zillow",
    )
    if len(housing_pts) < 8:
        housing_pts = series_for(
            geo_id,
            "zhvi",
            limit=window_weeks + 4,
            provider="zillow",
        )
    equity = macro_series("GSPC")
    mortgage = macro_series("MORTGAGE30US")
    result = pearson_pairs(housing_pts[-window_weeks:], equity[-window_weeks:], mortgage[-window_weeks:])
    return CorrelationResponse(
        freshness=build_freshness(prefer_source="zillow:inv_week_metro"),
        geo_id=geo_id,
        aligned_cadence=result.aligned_cadence,
        n=result.n,
        status=result.status,
        pairs=result.pairs,
        disclaimer=result.disclaimer or DISCLAIMER,
    )
