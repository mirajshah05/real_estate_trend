"""Census 2024 ZCTA centroids + compact MSA/CBSA lookup for metro map pins."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import zipfile
from pathlib import Path

from realtykit.ingest.http import CachedHttp
from realtykit.log import utc_iso
from realtykit.providers.base import FetchOutcome
from realtykit.settings import Settings, get_settings
from realtykit.store.facts import upsert_geos
from realtykit.store.sources import upsert_source

ZCTA_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip"
CBSA_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_cbsa_national.zip"


def _read_zip_txt(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".txt"))
        return zf.read(name).decode("utf-8", errors="replace")


def _gazetteer_rows(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    rows = []
    for raw in reader:
        rows.append({(k or "").strip(): (v or "").strip() for k, v in raw.items()})
    return rows


def _load_compact_msa(settings: Settings) -> list[dict]:
    path = settings.fixtures_dir / "msa_centroids.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("metros") or []


def ingest(
    conn: sqlite3.Connection, settings: Settings | None = None, force: bool = False
) -> list[FetchOutcome]:
    settings = settings or get_settings()
    http = CachedHttp(settings)
    return [
        _zcta(conn, http, settings, force),
        _msa(conn, http, settings, force),
    ]


def _zcta(
    conn: sqlite3.Connection, http: CachedHttp, settings: Settings, force: bool
) -> FetchOutcome:
    fetched_at = utc_iso()
    try:
        cached = http.get_cached(ZCTA_URL, "census/2024_Gaz_zcta_national.zip", force=force)
        text = _read_zip_txt(cached.path)
        geos: list[dict] = []
        for row in _gazetteer_rows(text):
            geoid = (row.get("GEOID") or "").strip()
            if not geoid:
                continue
            try:
                lat = float((row.get("INTPTLAT") or "").strip())
                lon = float((row.get("INTPTLONG") or "").strip())
            except ValueError:
                continue
            geos.append(
                {
                    "geo_id": f"census:zcta:{geoid}",
                    "level": "zip",
                    "name": geoid,
                    "state": None,
                    "lat": lat,
                    "lon": lon,
                }
            )
        if geos:
            upsert_geos(geos, conn)
        out = FetchOutcome(
            source_id="census:zcta_2024",
            provider="census",
            dataset="zcta_gazetteer_2024",
            url=ZCTA_URL,
            status="ok",
            fetched_at=cached.fetched_at,
            cadence="unknown",
            observation_as_of="2024-08-30",
            http_last_modified=cached.last_modified,
            etag=cached.etag,
            content_sha256=cached.content_sha256,
            bytes=cached.bytes,
            freshness="by_design_monthly",
            note=f"Reference geography. {len(geos)} ZCTA centroids. Not a market freshness source.",
            path=cached.path,
            rows_upserted=len(geos),
        )
    except Exception as exc:  # noqa: BLE001
        out = FetchOutcome(
            source_id="census:zcta_2024",
            provider="census",
            dataset="zcta_gazetteer_2024",
            url=ZCTA_URL,
            status="error",
            fetched_at=fetched_at,
            cadence="unknown",
            freshness="unavailable",
            note=f"ZCTA fetch failed: {exc}",
        )
    upsert_source(out.as_source_row(), conn)
    return out


def _msa(
    conn: sqlite3.Connection, http: CachedHttp, settings: Settings, force: bool
) -> FetchOutcome:
    """Prefer Census CBSA gazetteer; always apply compact JSON so metros can map."""
    fetched_at = utc_iso()
    compact = _load_compact_msa(settings)
    applied = 0
    if compact:
        existing = {
            r["name"]: r
            for r in conn.execute(
                "SELECT geo_id, name FROM geos WHERE level IN ('metro','nation')"
            ).fetchall()
        }
        updates = []
        for m in compact:
            name = m.get("name")
            match = existing.get(name)
            if not match:
                continue
            updates.append(
                {
                    "geo_id": match["geo_id"],
                    "level": "nation" if match["geo_id"] == "nation:US" else "metro",
                    "name": name,
                    "state": m.get("state"),
                    "lat": m.get("lat"),
                    "lon": m.get("lon"),
                }
            )
        if updates:
            upsert_geos(updates, conn)
            applied = len(updates)

    note = f"Applied {applied} compact MSA centroids from fixtures."
    last_modified = None
    digest = None
    size = None
    path = None
    try:
        cached = http.get_cached(CBSA_URL, "census/2024_Gaz_cbsa_national.zip", force=force)
        last_modified = cached.last_modified
        digest = cached.content_sha256
        size = cached.bytes
        path = cached.path
        text = _read_zip_txt(cached.path)
        cbsa = []
        for row in _gazetteer_rows(text):
            name = (row.get("NAME") or "").strip()
            try:
                lat = float((row.get("INTPTLAT") or "").strip())
                lon = float((row.get("INTPTLONG") or "").strip())
            except ValueError:
                continue
            cbsa.append((name, lat, lon))
        matched = _match_cbsa(conn, cbsa)
        if matched:
            upsert_geos(matched, conn)
            note += f" Census CBSA matched {len(matched)} metros."
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        note += f" CBSA gazetteer skipped ({exc}). Compact JSON still used."
        status = "ok" if applied else "error"

    out = FetchOutcome(
        source_id="census:cbsa_2024",
        provider="census",
        dataset="cbsa_gazetteer_2024",
        url=CBSA_URL,
        status=status,
        fetched_at=fetched_at,
        cadence="unknown",
        observation_as_of="2024",
        http_last_modified=last_modified,
        content_sha256=digest,
        bytes=size,
        freshness="by_design_monthly",
        note=note,
        path=path,
        rows_upserted=applied,
    )
    upsert_source(out.as_source_row(), conn)
    return out


def _match_cbsa(conn: sqlite3.Connection, cbsa: list[tuple[str, float, float]]) -> list[dict]:
    metros = conn.execute("SELECT geo_id, name, state FROM geos WHERE level = 'metro'").fetchall()
    out: list[dict] = []
    for metro in metros:
        name = metro["name"] or ""
        if ", " not in name:
            continue
        city, state = name.rsplit(", ", 1)
        city_l = city.lower()
        state_l = state.lower()
        hit = None
        for cbsa_name, lat, lon in cbsa:
            low = cbsa_name.lower()
            if (city_l in low.split("-")[0] or low.startswith(city_l)) and state_l in low:
                hit = (lat, lon)
                break
        if hit:
            out.append(
                {
                    "geo_id": metro["geo_id"],
                    "level": "metro",
                    "name": name,
                    "state": metro["state"],
                    "lat": hit[0],
                    "lon": hit[1],
                }
            )
    return out
