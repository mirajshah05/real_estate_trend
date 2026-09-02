"""Yahoo chart API for ^GSPC and ^IXIC. User-Agent + backoff. No yfinance."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from realtykit.freshness import classify
from realtykit.ingest.http import CachedHttp
from realtykit.log import utc_iso
from realtykit.providers.base import FetchOutcome
from realtykit.settings import Settings, get_settings
from realtykit.store.facts import upsert_macro
from realtykit.store.sources import upsert_source

SYMBOLS = (
    ("^GSPC", "GSPC", "yahoo_gspc.json"),
    ("^IXIC", "IXIC", "yahoo_ixic.json"),
    ("^DJI", "DJI", "yahoo_dji.json"),
)
CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def _to_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def ingest(conn: sqlite3.Connection, settings: Settings | None = None, force: bool = False) -> list[FetchOutcome]:
    settings = settings or get_settings()
    http = CachedHttp(settings)
    return [_one(conn, http, symbol, series_id, probe, force) for symbol, series_id, probe in SYMBOLS]


def _one(
    conn: sqlite3.Connection,
    http: CachedHttp,
    symbol: str,
    series_id: str,
    probe: str,
    force: bool,
) -> FetchOutcome:
    url = CHART.format(symbol=symbol) + "?interval=1wk&range=2y"
    fetched_at = utc_iso()
    try:
        cached = http.get_cached(
            url,
            f"yahoo/{series_id}_week.json",
            force=force,
            retries=4,
            backoff=2.0,
            extra_headers={"Accept": "application/json"},
            probe_name=probe,
        )
        payload = json.loads(cached.path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        out = FetchOutcome(
            source_id=f"yahoo:{series_id}",
            provider="yahoo",
            dataset=f"chart_{series_id}",
            url=url,
            status="error",
            fetched_at=fetched_at,
            cadence="weekly",
            freshness="unavailable",
            note=f"yahoo fetch failed: {exc}",
        )
        upsert_source(out.as_source_row(), conn)
        return out

    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        out = FetchOutcome(
            source_id=f"yahoo:{series_id}",
            provider="yahoo",
            dataset=f"chart_{series_id}",
            url=url,
            status="error",
            fetched_at=cached.fetched_at,
            cadence="weekly",
            freshness="unavailable",
            note="empty chart result",
        )
        upsert_source(out.as_source_row(), conn)
        return out

    timestamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
    meta = result.get("meta") or {}
    points: list[dict] = []
    latest = None
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        day = _to_date(int(ts))
        latest = day
        points.append(
            {
                "series_id": series_id,
                "ts": day,
                "value": float(close),
                "provider": "yahoo",
                "source_id": f"yahoo:{series_id}",
            }
        )
    if points:
        upsert_macro(points, conn)

    # Daily 5d for last/1d delta
    daily_url = CHART.format(symbol=symbol) + "?interval=1d&range=5d"
    try:
        daily = http.get_cached(
            daily_url,
            f"yahoo/{series_id}_5d.json",
            force=force,
            retries=3,
            extra_headers={"Accept": "application/json"},
            probe_name=probe.replace(".json", "_5d.json") if probe.endswith(".json") else None,
        )
        dpayload = json.loads(daily.path.read_text(encoding="utf-8"))
        dres = ((dpayload.get("chart") or {}).get("result") or [None])[0]
        if dres:
            dts = dres.get("timestamp") or []
            dclose = (((dres.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
            dpoints = []
            for ts, close in zip(dts, dclose):
                if close is None:
                    continue
                day = _to_date(int(ts))
                latest = day
                dpoints.append(
                    {
                        "series_id": f"{series_id}_D",
                        "ts": day,
                        "value": float(close),
                        "provider": "yahoo",
                        "source_id": f"yahoo:{series_id}",
                    }
                )
            if dpoints:
                upsert_macro(dpoints, conn)
    except Exception:  # noqa: BLE001
        pass

    last = meta.get("regularMarketPrice")
    status, _ = classify(observation_as_of=latest, cadence="daily")
    out = FetchOutcome(
        source_id=f"yahoo:{series_id}",
        provider="yahoo",
        dataset=f"chart_{series_id}",
        url=url,
        status="ok",
        fetched_at=cached.fetched_at,
        cadence="daily",
        observation_as_of=latest,
        http_last_modified=cached.last_modified,
        etag=cached.etag,
        content_sha256=cached.content_sha256,
        bytes=cached.bytes,
        freshness=status,
        note=f"{symbol} last {last} as of {latest}. 52w high {meta.get('fiftyTwoWeekHigh')} low {meta.get('fiftyTwoWeekLow')}.",
        path=cached.path,
        rows_upserted=len(points),
        extra={
            "last": last,
            "high_52w": meta.get("fiftyTwoWeekHigh"),
            "low_52w": meta.get("fiftyTwoWeekLow"),
        },
    )
    upsert_source(out.as_source_row(), conn)
    return out
