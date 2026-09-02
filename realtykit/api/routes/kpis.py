from __future__ import annotations

from fastapi import APIRouter, Depends

from realtykit.api.deps import ensure_store, geo_param
from realtykit.api.schemas import KpisResponse
from realtykit.freshness import build_freshness, source_block
from realtykit.models.market import KpiPoint
from realtykit.store.db import connect
from realtykit.store.facts import get_geo, series_for
from realtykit.store.sources import get_source

router = APIRouter()


def _delta(series: list[tuple[str, float]], steps: int) -> float | None:
    if len(series) <= steps:
        return None
    cur, prev = series[-1][1], series[-1 - steps][1]
    if prev == 0:
        return None
    return (cur - prev) / prev


def _abs_delta(series: list[tuple[str, float]], steps: int) -> float | None:
    if len(series) <= steps:
        return None
    return series[-1][1] - series[-1 - steps][1]


@router.get("/kpis", response_model=KpisResponse)
def kpis(geo_id: str = Depends(geo_param), _ok: None = Depends(ensure_store)) -> KpisResponse:
    conn = connect()
    try:
        geo = get_geo(geo_id, conn)
        inv = series_for(geo_id, "inventory", provider="zillow", cadence="weekly", conn=conn)
        nl = series_for(geo_id, "new_listings", provider="zillow", cadence="weekly", conn=conn)
        dom = series_for(geo_id, "days_on_market", provider="zillow", cadence="weekly", conn=conn)
        zhvi = series_for(geo_id, "zhvi", provider="zillow", cadence="monthly", conn=conn)
        mort = conn.execute(
            "SELECT ts, value FROM macro_series WHERE series_id = 'MORTGAGE30US' ORDER BY ts"
        ).fetchall()
        spx = conn.execute(
            "SELECT ts, value FROM macro_series WHERE series_id IN ('GSPC_D','GSPC') ORDER BY ts"
        ).fetchall()
    finally:
        conn.close()

    inv_src = get_source("zillow:inv_week_metro")
    zhvi_src = get_source("zillow:zhvi_metro")
    fred_src = get_source("fred:MORTGAGE30US")
    yahoo_src = get_source("yahoo:GSPC")

    def st(src: dict | None, default: str = "stale") -> str:
        if not src:
            return default
        return source_block(src).status

    mort_pts = [(r["ts"], float(r["value"])) for r in mort]
    spx_pts = [(r["ts"], float(r["value"])) for r in spx]
    drawdown = None
    if spx_pts:
        window = [v for _, v in spx_pts[-52:]]
        last = window[-1]
        high = max(window)
        drawdown = (last - high) / high if high else None

    as_of = inv[-1][0] if inv else (zhvi[-1][0] if zhvi else None)
    kpis_out = {
        "zhvi": KpiPoint(
            value=round(zhvi[-1][1]) if zhvi else None,
            delta_mom=_delta(zhvi, 1),
            delta_yoy=_delta(zhvi, 12),
            status=st(zhvi_src, "by_design_monthly"),
        ),
        "inventory": KpiPoint(
            value=inv[-1][1] if inv else None,
            delta_wow=_delta(inv, 1),
            delta_yoy=_delta(inv, 52),
            status=st(inv_src),
        ),
        "new_listings": KpiPoint(
            value=nl[-1][1] if nl else None,
            delta_wow=_delta(nl, 1),
            delta_yoy=_delta(nl, 52),
            status=st(inv_src),
        ),
        "days_on_market": KpiPoint(
            value=dom[-1][1] if dom else None,
            delta_wow=_abs_delta(dom, 1),
            delta_yoy=_abs_delta(dom, 52),
            status=st(inv_src),
        ),
        "mortgage_30y": KpiPoint(
            value=mort_pts[-1][1] if mort_pts else None,
            delta_wow=_abs_delta(mort_pts, 1) if mort_pts else None,
            delta_yoy=_abs_delta(mort_pts, 52) if mort_pts else None,
            status=st(fred_src, "unavailable"),
        ),
        "spx": KpiPoint(
            value=spx_pts[-1][1] if spx_pts else None,
            delta_1d=_delta(spx_pts, 1) if spx_pts else None,
            drawdown_52w=drawdown,
            status=st(yahoo_src, "live"),
        ),
    }
    return KpisResponse(
        freshness=build_freshness(prefer_source="zillow:inv_week_metro"),
        geo_id=geo_id,
        name=geo["name"] if geo else None,
        as_of=as_of,
        kpis=kpis_out,
    )
