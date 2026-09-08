from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from realtykit.api.deps import ensure_store, geo_param
from realtykit.api.schemas import METRICS, TrendPoint, TrendsResponse
from realtykit.freshness import build_freshness
from realtykit.store.facts import macro_series, series_for
from realtykit.store.sources import get_source

router = APIRouter()

DEFAULT_METRICS = ("inventory", "days_on_market", "new_listings", "zhvi")
MACRO_SERIES = {
    "gspc": "GSPC",
    "mortgage_30y": "MORTGAGE30US",
}
FACT_SOURCES = {
    "inventory": "zillow:inv_week_metro",
    "days_on_market": "zillow:dom_week_metro",
    "new_listings": "zillow:new_listings_week_metro",
    "zhvi": "zillow:zhvi_metro",
    "price_change_mom": "zillow:zhvi_metro",
    "price_change_yoy": "zillow:zhvi_metro",
    "inventory_wow": "zillow:inv_week_metro",
    "inventory_yoy": "zillow:inv_week_metro",
}
FACT_CADENCE_OVERRIDES = {
    # The combined Overlay intentionally mixes monthly housing values with
    # weekly comparison series. Do not discard ZHVI when the page requests its
    # usual weekly trend payload.
    "zhvi": "monthly",
}
MACRO_SOURCES = {
    "GSPC": "yahoo:GSPC",
    "MORTGAGE30US": "fred:MORTGAGE30US",
}


def _valid_date(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_date", "message": f"{name} must be YYYY-MM-DD."},
        ) from None
    return value


def _monthly(points: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Use the last available observation in each calendar month."""
    by_month: dict[str, tuple[str, float]] = {}
    for ts, value in points:
        by_month[ts[:7]] = (ts, value)
    return [by_month[key] for key in sorted(by_month)]


def _macro_points(
    series_id: str,
    cadence: str,
    from_date: str | None,
    to_date: str | None,
) -> list[tuple[str, float]]:
    points = macro_series(series_id, from_ts=from_date, to_ts=to_date)
    return _monthly(points) if cadence == "monthly" else points[-260:]


def _freshness(names: list[str]):
    source_ids = {FACT_SOURCES[name] for name in names if name in FACT_SOURCES}
    source_ids.update(MACRO_SOURCES[MACRO_SERIES[name]] for name in names if name in MACRO_SERIES)
    rows = [source for source_id in source_ids if (source := get_source(source_id))]
    preferred = next(iter(source_ids), None)
    return build_freshness(rows=rows or None, prefer_source=preferred)


@router.get("/trends", response_model=TrendsResponse)
def trends(
    geo_id: str = Depends(geo_param),
    metrics: str = Query(default="inventory,days_on_market,new_listings,zhvi"),
    cadence: Literal["weekly", "monthly"] = Query(default="weekly"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    _ok: None = Depends(ensure_store),
) -> TrendsResponse:
    from_date = _valid_date(from_date, "from")
    to_date = _valid_date(to_date, "to")
    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_date_range", "message": "from must be on or before to."},
        )

    names = [m.strip() for m in metrics.split(",") if m.strip()]
    names = names or list(DEFAULT_METRICS)
    unknown = [name for name in names if name not in METRICS]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail={"code": "unknown_metric", "message": f"Unknown metric: {unknown[0]}"},
        )
    names = names[:8]

    series: dict[str, list[TrendPoint]] = {}
    for name in names:
        if name in MACRO_SERIES:
            points = _macro_points(MACRO_SERIES[name], cadence, from_date, to_date)
        else:
            fact_cadence = FACT_CADENCE_OVERRIDES.get(name, cadence)
            points = series_for(
                geo_id,
                name,
                limit=260,
                provider="zillow",
                cadence=fact_cadence,
                from_period=from_date,
                to_period=to_date,
            )
        series[name] = [TrendPoint(t=ts, v=value) for ts, value in points]

    return TrendsResponse(
        freshness=_freshness(names),
        geo_id=geo_id,
        cadence=cadence,
        series=series,
    )
