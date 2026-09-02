from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from realtykit.analysis.constants import OUTLIER_Z_ABS
from realtykit.analysis.outliers import listing_outliers, metro_zscore_outliers
from realtykit.api.deps import ensure_store, geo_param
from realtykit.api.schemas import OutliersResponse
from realtykit.freshness import build_freshness
from realtykit.store.db import connect
from realtykit.store.facts import latest_facts

router = APIRouter()


@router.get("/outliers", response_model=OutliersResponse)
def outliers(
    geo_id: str = Depends(geo_param),
    kind: str = Query(default="geo"),
    metric: str = Query(default="inventory_wow"),
    limit: int = Query(default=25, ge=1, le=100),
    _ok: None = Depends(ensure_store),
) -> OutliersResponse:
    if kind in {"listing", "all"}:
        conn = connect()
        try:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM listings WHERE geo_id = ? OR ? = 'nation:US'",
                    (geo_id, geo_id),
                ).fetchall()
            ]
        finally:
            conn.close()
        zhvi = latest_facts("zhvi", geo_id=geo_id)
        dom = latest_facts("days_on_market", geo_id=geo_id)
        median_price = zhvi[0]["value"] if zhvi else None
        median_dom = dom[0]["value"] if dom else None
        found = listing_outliers(rows, city_median_price=median_price, city_median_dom=median_dom)
        if kind == "listing" or found:
            return OutliersResponse(
                freshness=build_freshness(prefer_source="rentcast:listings"),
                kind="listing",
                method="price_dom_multiples",
                label="listing outliers",
                rows=found[:limit],
            )

    wanted = (
        metric
        if metric in {"inventory_wow", "days_on_market", "zhvi_mom", "price_change_mom"}
        else "inventory_wow"
    )
    store_metric = "price_change_mom" if wanted == "zhvi_mom" else wanted
    facts = latest_facts(store_metric)
    cohort = [
        {"geo_id": r["geo_id"], "name": r.get("name") or r["geo_id"], "value": r["value"]}
        for r in facts
        if r.get("level") == "metro" and r.get("value") is not None
    ]
    rows = metro_zscore_outliers(cohort, metric=store_metric, z_abs=OUTLIER_Z_ABS)
    return OutliersResponse(
        freshness=build_freshness(prefer_source="zillow:inv_week_metro"),
        kind="geo",
        method="metro_zscore",
        label="market outliers",
        rows=rows[:limit],
    )
