"""Load probe-derived fixtures into SQLite when the serving store is empty."""

from __future__ import annotations

import json
from pathlib import Path

from realtykit.log import log, utc_iso
from realtykit.settings import Settings, get_settings
from realtykit.store.db import connect, init_db
from realtykit.store.facts import fact_count, upsert_facts, upsert_geos, upsert_macro
from realtykit.store.sources import upsert_source


def load_snapshot(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    path = settings.fixtures_dir / "snapshot.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def seed_if_empty(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    conn = init_db(settings=settings)
    if fact_count(conn) > 0:
        conn.close()
        return False
    snap = load_snapshot(settings)
    if not snap:
        conn.close()
        return False
    apply_snapshot(snap, conn)
    conn.commit()
    conn.close()
    log("seeded_fixtures", facts=len(snap.get("map_cities") or []))
    return True


def apply_snapshot(snap: dict, conn) -> None:
    fetched = utc_iso()
    for src in snap.get("sources") or []:
        upsert_source(
            {
                **src,
                "fetched_at": src.get("fetched_at") or fetched,
                "etag": src.get("etag"),
                "content_sha256": src.get("content_sha256"),
                "bytes": src.get("bytes"),
            },
            conn,
        )

    geos = snap.get("geos") or []
    if geos:
        upsert_geos(geos, conn)

    facts: list[dict] = []
    housing_week = snap.get("housing_week") or "2026-08-15"
    zhvi_month = snap.get("zhvi_month") or "2026-07-31"

    for city in snap.get("map_cities") or []:
        gid = city["geo_id"]
        if city.get("inventory") is not None:
            facts.append(_fact(gid, housing_week, "inventory", city["inventory"], "zillow", "zillow:inv_week_metro"))
        if city.get("price") is not None:
            facts.append(_fact(gid, zhvi_month, "zhvi", city["price"], "zillow", "zillow:zhvi_metro"))
        if city.get("days_on_market") is not None:
            facts.append(_fact(gid, housing_week, "days_on_market", city["days_on_market"], "zillow", "zillow:dom_week_metro"))
        if city.get("new_listings") is not None:
            facts.append(_fact(gid, housing_week, "new_listings", city["new_listings"], "zillow", "zillow:new_listings_week_metro"))
        if city.get("mom") is not None:
            facts.append(_fact(gid, zhvi_month, "price_change_mom", city["mom"], "zillow", "zillow:zhvi_metro"))
        if city.get("yoy") is not None:
            facts.append(_fact(gid, zhvi_month, "price_change_yoy", city["yoy"], "zillow", "zillow:zhvi_metro"))
        if city.get("inventory_mom") is not None:
            facts.append(_fact(gid, housing_week, "inventory_wow", city["inventory_mom"], "zillow", "zillow:inv_week_metro"))

    for gid, series in (snap.get("trends") or {}).items():
        for metric, pts in series.items():
            source = {
                "inventory": "zillow:inv_week_metro",
                "days_on_market": "zillow:dom_week_metro",
                "new_listings": "zillow:new_listings_week_metro",
                "zhvi": "zillow:zhvi_metro",
            }.get(metric, "zillow:inv_week_metro")
            cadence = "monthly" if metric == "zhvi" else "weekly"
            for pt in pts:
                facts.append(_fact(gid, pt["t"], metric, pt["v"], "zillow", source, cadence))

    if facts:
        upsert_facts(facts, conn)

    macro: list[dict] = []
    stocks = snap.get("stocks") or {}
    for symbol, payload in stocks.items():
        series_id = "GSPC" if "GSPC" in symbol else "IXIC"
        for pt in payload.get("weekly") or []:
            macro.append(
                {
                    "series_id": series_id,
                    "ts": pt["t"],
                    "value": pt["v"],
                    "provider": "yahoo",
                    "source_id": f"yahoo:{series_id}",
                }
            )
        for pt in payload.get("daily") or []:
            macro.append(
                {
                    "series_id": f"{series_id}_D",
                    "ts": pt["t"],
                    "value": pt["v"],
                    "provider": "yahoo",
                    "source_id": f"yahoo:{series_id}",
                }
            )
    if macro:
        upsert_macro(macro, conn)

    redfin = snap.get("redfin_national_latest")
    if redfin:
        gid = "nation:US"
        pe = redfin["period_end"]
        mapping = {
            "median_sale_price": redfin.get("median_sale_price"),
            "inventory": redfin.get("inventory"),
            "new_listings": redfin.get("new_listings"),
            "median_dom": redfin.get("median_dom"),
            "homes_sold": redfin.get("homes_sold"),
        }
        extra = [
            _fact(gid, pe, metric, value, "redfin", "redfin:national_month", "monthly")
            for metric, value in mapping.items()
            if value is not None
        ]
        # Don't overwrite Zillow inventory for US with stale Redfin — store as distinct provider.
        upsert_facts(extra, conn)


def _fact(
    geo_id: str,
    period_end: str,
    metric: str,
    value: float,
    provider: str,
    source_id: str,
    cadence: str = "weekly",
) -> dict:
    return {
        "geo_id": geo_id,
        "period_end": period_end,
        "metric": metric,
        "value": value,
        "provider": provider,
        "source_id": source_id,
        "cadence": cadence,
    }


def write_run(run_id: str, started_at: str, finished_at: str, ok: bool, summary: dict) -> None:
    conn = connect()
    conn.execute(
        """
        INSERT INTO ingest_runs (run_id, started_at, finished_at, ok, summary_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, started_at, finished_at, 1 if ok else 0, json.dumps(summary)),
    )
    conn.commit()
    conn.close()


def fixture_path(name: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.fixtures_dir / name
