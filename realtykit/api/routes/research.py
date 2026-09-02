"""Cached, source-aware area research assembled from the serving database."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from realtykit.api.deps import ensure_store, geo_param
from realtykit.api.schemas import (
    ResearchMetric,
    ResearchPoint,
    ResearchResponse,
    ResearchSource,
)
from realtykit.freshness import build_freshness, source_block
from realtykit.store.db import connect
from realtykit.store.facts import get_geo

router = APIRouter()

AREA_METRICS = (
    "zhvi",
    "median_sale_price",
    "homes_sold",
    "inventory",
    "new_listings",
    "days_on_market",
    "median_dom",
    "price_change_yoy",
    "price_change_mom",
)
METRIC_LABELS = {
    "zhvi": "Typical home value (ZHVI)",
    "median_sale_price": "Median sale price",
    "homes_sold": "Homes sold",
    "inventory": "Inventory",
    "new_listings": "New listings",
    "days_on_market": "Days on market",
    "median_dom": "Median days on market",
    "price_change_yoy": "Value change YoY",
    "price_change_mom": "Value change MoM",
}
PROVIDER_PRIORITY = {"redfin": 0, "zillow": 1, "fhfa": 2}


def _fact_rows(
    conn: sqlite3.Connection, geo_id: str, *, national: bool = False
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT f.*, s.provider AS source_provider, s.dataset, s.url,
               s.http_last_modified, s.observation_as_of, s.freshness,
               s.note AS source_note
        FROM market_facts f
        LEFT JOIN sources s ON s.source_id = f.source_id
        WHERE f.geo_id = ? AND f.metric IN ({})
        ORDER BY f.metric, f.period_end
        """.format(",".join("?" for _ in AREA_METRICS)),
        (geo_id, *AREA_METRICS),
    ).fetchall()


def _preferred_rows(rows: list[sqlite3.Row]) -> dict[str, list[sqlite3.Row]]:
    by_metric: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_metric.setdefault(row["metric"], []).append(row)
    preferred: dict[str, list[sqlite3.Row]] = {}
    for metric, candidates in by_metric.items():
        providers = {row["provider"] for row in candidates}
        provider = min(providers, key=lambda p: PROVIDER_PRIORITY.get(p, 99))
        preferred[metric] = [row for row in candidates if row["provider"] == provider]
    return preferred


def _source(row: sqlite3.Row) -> ResearchSource:
    raw = dict(row)
    raw["source_id"] = raw.get("source_id") or ""
    raw["provider"] = raw.get("source_provider") or raw.get("provider") or ""
    raw["status"] = source_block(raw).status
    return ResearchSource(
        source_id=raw["source_id"],
        provider=raw["provider"],
        dataset=raw.get("dataset") or "",
        url=raw.get("url") or "",
        status=raw["status"],
        observation_as_of=raw.get("observation_as_of"),
        http_last_modified=raw.get("http_last_modified"),
        cadence=raw.get("cadence") or "unknown",
        note=raw.get("source_note") or raw.get("note") or "",
    )


def _metric(row: sqlite3.Row | None, metric: str) -> ResearchMetric:
    if row is None:
        return ResearchMetric(metric=metric, label=METRIC_LABELS[metric])
    source_status = source_block(dict(row)).status
    return ResearchMetric(
        metric=metric,
        label=METRIC_LABELS[metric],
        value=float(row["value"]) if row["value"] is not None else None,
        period_end=row["period_end"],
        cadence=row["cadence"],
        provider=row["provider"],
        source_id=row["source_id"],
        status=source_status,
    )


def _mortgage(conn: sqlite3.Connection) -> tuple[float, str] | None:
    row = conn.execute(
        "SELECT value, ts FROM macro_series WHERE series_id = 'MORTGAGE30US' ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None
    return float(row["value"]), row["ts"]


@router.get("/research", response_model=ResearchResponse)
def research(
    geo_id: str = Depends(geo_param),
    months: int = Query(default=36, ge=6, le=120),
    _ok: None = Depends(ensure_store),
) -> ResearchResponse:
    conn = connect()
    try:
        geo = get_geo(geo_id, conn)
        local = _preferred_rows(_fact_rows(conn, geo_id))
        national = _preferred_rows(_fact_rows(conn, "nation:US", national=True))
        source_ids = {
            row["source_id"]
            for rows in [*local.values(), *national.values()]
            for row in rows
            if row["source_id"]
        }
        macro = _mortgage(conn)
        fred = conn.execute(
            "SELECT * FROM sources WHERE source_id = 'fred:MORTGAGE30US'"
        ).fetchone()
        if fred:
            source_ids.add(fred["source_id"])
    finally:
        conn.close()

    metrics = [_metric(rows[-1] if rows else None, metric) for metric, rows in local.items()]
    present = {item.metric for item in metrics}
    metrics.extend(_metric(None, metric) for metric in AREA_METRICS if metric not in present)
    metrics.sort(key=lambda item: AREA_METRICS.index(item.metric))

    series: dict[str, list[ResearchPoint]] = {}
    for metric, rows in local.items():
        rows = rows[-months:]
        series[metric] = [
            ResearchPoint(t=row["period_end"], v=float(row["value"]))
            for row in rows
            if row["value"] is not None
        ]

    national_context = [
        _metric(rows[-1] if rows else None, metric) for metric, rows in national.items()
    ]
    national_context.sort(key=lambda item: AREA_METRICS.index(item.metric))

    source_rows: list[ResearchSource] = []
    all_source_rows = []
    source_conn = connect()
    try:
        for source_id in sorted(source_ids):
            row = source_conn.execute(
                "SELECT * FROM sources WHERE source_id = ?", (source_id,)
            ).fetchone()
            if row:
                all_source_rows.append(row)
    finally:
        source_conn.close()
    source_rows = [_source(row) for row in all_source_rows]

    insights: list[str] = []
    zhvi = series.get("zhvi", [])
    if len(zhvi) >= 2 and zhvi[-2].v:
        change = (zhvi[-1].v - zhvi[-2].v) / zhvi[-2].v
        insights.append(
            f"Typical home value changed {change:+.1%} over the latest stored observation."
        )
    inventory = series.get("inventory", [])
    if len(inventory) >= 2 and inventory[-2].v:
        change = (inventory[-1].v - inventory[-2].v) / inventory[-2].v
        insights.append(f"Inventory changed {change:+.1%} over the latest stored observation.")
    if metrics and not any(
        item.metric == "median_sale_price" and item.value is not None for item in metrics
    ):
        insights.append(
            "No actual sold-home price ledger is cached for this area; value estimates "
            "and indexes are not sale prices."
        )
    if macro:
        rate_status = source_block(dict(fred)).status if fred else "unavailable"
        metrics.append(
            ResearchMetric(
                metric="mortgage_30y",
                label="30-year mortgage rate",
                value=macro[0],
                period_end=macro[1],
                cadence="weekly",
                provider="fred",
                source_id="fred:MORTGAGE30US",
                status=rate_status,
            )
        )
        insights.append(f"Latest cached 30-year mortgage rate is {macro[0]:.2f}% as of {macro[1]}.")
    if not insights:
        insights.append("Refresh Zillow, Redfin, and FRED to populate this area's research cache.")

    preferred_source = "zillow:inv_week_metro" if local else "redfin:national_month"
    return ResearchResponse(
        freshness=build_freshness(prefer_source=preferred_source),
        geo_id=geo_id,
        name=geo["name"] if geo else None,
        state=geo["state"] if geo else None,
        as_of=next((item.period_end for item in metrics if item.period_end), None),
        metrics=metrics,
        series=series,
        national_context=national_context,
        sources=source_rows,
        insights=insights,
        disclaimers=[
            "Zillow ZHVI is an estimated home value, not a transaction price.",
            (
                "Redfin sale prices and homes sold are aggregate market statistics; the public "
                "Redfin feed is not a parcel ledger."
            ),
            "Mortgage rates are a national survey series and are not a borrower-specific quote.",
            (
                "Observation dates and publication/file dates are kept separately so delayed "
                "releases are not presented as live data."
            ),
        ],
    )
