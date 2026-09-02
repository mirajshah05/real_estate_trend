"""Redfin Data Center — national TSV only. Skip objects > 20 MB."""

from __future__ import annotations

import sqlite3

from realtykit.ingest.http import CachedHttp
from realtykit.ingest.stream_tsv import iter_tsv_gz
from realtykit.log import log, utc_iso
from realtykit.providers.base import FetchOutcome
from realtykit.settings import Settings, get_settings
from realtykit.store.facts import upsert_facts, upsert_geos
from realtykit.store.sources import upsert_source

NATIONAL_URL = (
    "https://redfin-public-data.s3.us-west-2.amazonaws.com/"
    "redfin_market_tracker/us_national_market_tracker.tsv000.gz"
)
MAX_BYTES = 20 * 1024 * 1024
KEEP = {
    "PERIOD_BEGIN",
    "PERIOD_END",
    "PERIOD_DURATION",
    "REGION",
    "PROPERTY_TYPE",
    "MEDIAN_SALE_PRICE",
    "NEW_LISTINGS",
    "INVENTORY",
    "MEDIAN_DOM",
    "HOMES_SOLD",
    "LAST_UPDATED",
}
METRIC_MAP = {
    "MEDIAN_SALE_PRICE": "median_sale_price",
    "NEW_LISTINGS": "new_listings",
    "INVENTORY": "inventory",
    "MEDIAN_DOM": "median_dom",
    "HOMES_SOLD": "homes_sold",
}


def ingest(conn: sqlite3.Connection, settings: Settings | None = None, force: bool = False) -> FetchOutcome:
    settings = settings or get_settings()
    http = CachedHttp(settings)
    fetched_at = utc_iso()
    try:
        head = http.head(NATIONAL_URL, timeout=20)
        length = int(head.headers.get("Content-Length") or 0)
        if length > MAX_BYTES:
            out = FetchOutcome(
                source_id="redfin:national_month",
                provider="redfin",
                dataset="us_national_market_tracker",
                url=NATIONAL_URL,
                status="skipped",
                fetched_at=fetched_at,
                cadence="monthly",
                http_last_modified=head.headers.get("Last-Modified"),
                freshness="stale",
                note=f"Skip: Content-Length {length} > 20MB cap.",
                bytes=length,
            )
            upsert_source(out.as_source_row(), conn)
            return out
    except Exception as exc:  # noqa: BLE001
        log("redfin_head_failed", error=str(exc))

    try:
        cached = http.get_cached(
            NATIONAL_URL,
            "redfin/us_national_market_tracker.tsv000.gz",
            max_bytes=MAX_BYTES,
            force=force,
        )
    except Exception as exc:  # noqa: BLE001
        out = FetchOutcome(
            source_id="redfin:national_month",
            provider="redfin",
            dataset="us_national_market_tracker",
            url=NATIONAL_URL,
            status="error",
            fetched_at=fetched_at,
            cadence="monthly",
            freshness="stale",
            note=f"national fetch failed: {exc}",
        )
        upsert_source(out.as_source_row(), conn)
        return out

    facts: list[dict] = []
    latest_end = None
    for row in iter_tsv_gz(cached.path, keep_columns=KEEP):
        period_end = row.get("PERIOD_END")
        if not period_end:
            continue
        if latest_end is None or period_end > latest_end:
            latest_end = period_end
        for col, metric in METRIC_MAP.items():
            raw = row.get(col)
            if raw in (None, ""):
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            facts.append(
                {
                    "geo_id": "nation:US",
                    "period_end": period_end,
                    "period_start": row.get("PERIOD_BEGIN"),
                    "metric": metric,
                    "value": value,
                    "provider": "redfin",
                    "source_id": "redfin:national_month",
                    "cadence": "monthly",
                }
            )
    upsert_geos(
        [{"geo_id": "nation:US", "level": "nation", "name": "United States", "state": None}],
        conn,
    )
    if facts:
        upsert_facts(facts, conn)
    out = FetchOutcome(
        source_id="redfin:national_month",
        provider="redfin",
        dataset="us_national_market_tracker",
        url=NATIONAL_URL,
        status="ok",
        fetched_at=cached.fetched_at,
        cadence="monthly",
        observation_as_of=latest_end,
        http_last_modified=cached.last_modified,
        etag=cached.etag,
        content_sha256=cached.content_sha256,
        bytes=cached.bytes,
        freshness="stale",
        note=(
            f"National only. Latest PERIOD_END {latest_end}. "
            "S3 object historically stuck; treat as history, not live."
        ),
        path=cached.path,
        rows_upserted=len(facts),
    )
    upsert_source(out.as_source_row(), conn)
    return out
