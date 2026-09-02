"""Zillow Research CSVs: weekly metro inventory / DOM / new listings + metro ZHVI."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime

from realtykit.freshness import classify
from realtykit.ingest.http import CachedHttp
from realtykit.ingest.stream_csv import latest_week, melt_wide_csv
from realtykit.log import utc_iso
from realtykit.providers.base import FetchOutcome
from realtykit.settings import Settings, get_settings
from realtykit.store.facts import upsert_facts, upsert_geos
from realtykit.store.sources import upsert_source

ZILLOW_BASE = "https://files.zillowstatic.com/research/public_csvs"

DATASETS = (
    {
        "source_id": "zillow:inv_week_metro",
        "dataset": "metro_inventory_week",
        "url": f"{ZILLOW_BASE}/invt_fs/Metro_invt_fs_uc_sfrcondo_sm_week.csv",
        "dest": "zillow/Metro_invt_fs_uc_sfrcondo_sm_week.csv",
        "probe": "Metro_invt_fs_uc_sfrcondo_sm_week.csv",
        "metric": "inventory",
        "cadence": "weekly",
        "keep_years": 5,
    },
    {
        "source_id": "zillow:dom_week_metro",
        "dataset": "metro_dom_week",
        "url": f"{ZILLOW_BASE}/mean_doz_pending/Metro_mean_doz_pending_uc_sfrcondo_sm_week.csv",
        "dest": "zillow/Metro_mean_doz_pending_uc_sfrcondo_sm_week.csv",
        "probe": "Metro_mean_doz_pending_uc_sfrcondo_sm_week.csv",
        "metric": "days_on_market",
        "cadence": "weekly",
        "keep_years": 5,
    },
    {
        "source_id": "zillow:new_listings_week_metro",
        "dataset": "metro_new_listings_week",
        "url": f"{ZILLOW_BASE}/new_listings/Metro_new_listings_uc_sfrcondo_sm_week.csv",
        "dest": "zillow/Metro_new_listings_uc_sfrcondo_sm_week.csv",
        "probe": "Metro_new_listings_uc_sfrcondo_sm_week.csv",
        "metric": "new_listings",
        "cadence": "weekly",
        "keep_years": 5,
    },
    {
        "source_id": "zillow:zhvi_metro",
        "dataset": "metro_zhvi_month",
        "url": f"{ZILLOW_BASE}/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
        "dest": "zillow/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
        "probe": "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
        "metric": "zhvi",
        "cadence": "monthly",
        "keep_years": 8,
    },
    {
        "source_id": "zillow:inv_week_zip",
        "dataset": "zip_inventory_week",
        "url": f"{ZILLOW_BASE}/invt_fs/Zip_invt_fs_uc_sfrcondo_sm_week.csv",
        "dest": "zillow/Zip_invt_fs_uc_sfrcondo_sm_week.csv",
        "metric": "inventory",
        "cadence": "weekly",
        "keep_years": 2,
        "level": "zip",
        "latest_only": True,
    },
)


def geo_id_for(region_id: str, region_type: str, name: str) -> str:
    if region_type == "country" or name == "United States":
        return "nation:US"
    if region_type.lower() in {"zip", "zipcode", "zcta"}:
        zip_code = str(name).strip().zfill(5)
        return f"zillow:zip:{zip_code}"
    return f"zillow:metro:{region_id}"


def _min_period(keep_years: int) -> str:
    today = datetime.now(UTC).date()
    return date(today.year - keep_years, today.month, 1).isoformat()


def ingest(
    conn: sqlite3.Connection, settings: Settings | None = None, force: bool = False
) -> list[FetchOutcome]:
    settings = settings or get_settings()
    http = CachedHttp(settings)
    outcomes: list[FetchOutcome] = []
    for spec in DATASETS:
        outcomes.append(_ingest_one(conn, http, spec, force))
    _derive_changes(conn)
    return outcomes


def _ingest_one(
    conn: sqlite3.Connection, http: CachedHttp, spec: dict, force: bool
) -> FetchOutcome:
    fetched_at = utc_iso()
    try:
        cached = http.get_cached(
            spec["url"],
            spec["dest"],
            force=force,
            probe_name=spec.get("probe"),
        )
    except Exception as exc:  # noqa: BLE001 — provider must not abort the run
        out = FetchOutcome(
            source_id=spec["source_id"],
            provider="zillow",
            dataset=spec["dataset"],
            url=spec["url"],
            status="error",
            fetched_at=fetched_at,
            cadence=spec["cadence"],
            note=f"fetch failed: {exc}",
        )
        upsert_source(out.as_source_row(), conn)
        return out

    obs = latest_week(cached.path)
    status, _hours = classify(
        observation_as_of=obs,
        cadence=spec["cadence"],
        http_last_modified=cached.last_modified,
        forced="by_design_monthly" if spec["cadence"] == "monthly" else None,
    )
    note = (
        f"Latest column {obs}. File LM {cached.last_modified or 'unknown'}. "
        "Observation clock is the 7-day SLA; weekly Zillow is often file-fresh / observation-stale."
        if spec["cadence"] == "weekly"
        else f"ZHVI month {obs}. Monthly by design — not a 7-day print."
    )
    geos: dict[str, dict] = {}
    facts: list[dict] = []
    for row in melt_wide_csv(
        cached.path,
        min_period=_min_period(spec["keep_years"]),
        latest_only=bool(spec.get("latest_only")),
    ):
        gid = geo_id_for(row["region_id"], row["region_type"], row["name"])
        geos[gid] = {
            "geo_id": gid,
            "level": "nation" if gid == "nation:US" else spec.get("level", "metro"),
            "name": str(row["name"]).strip().zfill(5)
            if spec.get("level") == "zip"
            else row["name"],
            "state": row["state"] or None,
        }
        facts.append(
            {
                "geo_id": gid,
                "period_end": row["period_end"],
                "metric": spec["metric"],
                "value": row["value"],
                "provider": "zillow",
                "source_id": spec["source_id"],
                "cadence": spec["cadence"],
            }
        )
    if geos:
        upsert_geos(list(geos.values()), conn)
    if facts:
        upsert_facts(facts, conn)
    out = FetchOutcome(
        source_id=spec["source_id"],
        provider="zillow",
        dataset=spec["dataset"],
        url=spec["url"],
        status="ok",
        fetched_at=cached.fetched_at,
        cadence=spec["cadence"],
        observation_as_of=obs,
        http_last_modified=cached.last_modified,
        etag=cached.etag,
        content_sha256=cached.content_sha256,
        bytes=cached.bytes,
        freshness=status,
        note=note,
        path=cached.path,
        rows_upserted=len(facts),
    )
    upsert_source(out.as_source_row(), conn)
    return out


def _derive_changes(conn: sqlite3.Connection) -> None:
    """MoM / YoY for ZHVI and WoW / YoY for weekly inventory from stored facts."""
    derived: list[dict] = []
    for metric, cadence, mom_name, yoy_name, mom_offset, yoy_offset in (
        ("zhvi", "monthly", "price_change_mom", "price_change_yoy", 1, 12),
        ("inventory", "weekly", "inventory_wow", "inventory_yoy", 1, 52),
    ):
        rows = conn.execute(
            """
            SELECT geo_id, period_end, value, source_id FROM market_facts
            WHERE metric = ? AND provider = 'zillow'
            ORDER BY geo_id, period_end
            """,
            (metric,),
        ).fetchall()
        by_geo: dict[str, list] = {}
        for r in rows:
            by_geo.setdefault(r["geo_id"], []).append(r)
        for gid, series in by_geo.items():
            if len(series) < 2:
                continue
            for index, current in enumerate(series):
                prev = series[index - mom_offset] if index >= mom_offset else None
                yoy = series[index - yoy_offset] if index >= yoy_offset else None
                if prev and prev["value"] not in (None, 0):
                    derived.append(
                        {
                            "geo_id": gid,
                            "period_end": current["period_end"],
                            "metric": mom_name,
                            "value": (current["value"] - prev["value"]) / prev["value"],
                            "provider": "zillow",
                            "source_id": current["source_id"],
                            "cadence": cadence,
                        }
                    )
                if yoy and yoy["value"] not in (None, 0):
                    derived.append(
                        {
                            "geo_id": gid,
                            "period_end": current["period_end"],
                            "metric": yoy_name,
                            "value": (current["value"] - yoy["value"]) / yoy["value"],
                            "provider": "zillow",
                            "source_id": current["source_id"],
                            "cadence": cadence,
                        }
                    )
    if derived:
        upsert_facts(derived, conn)
