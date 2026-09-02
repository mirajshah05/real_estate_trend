"""Free official Bay Area GIS reference layers with dated, auditable snapshots.

These feeds describe boundaries and parcels. They are deliberately not treated
as sale-price events: neither county endpoint publishes a reliable consideration
amount in the fields used here.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from realtykit.ingest.http import CachedFetch, CachedHttp
from realtykit.log import utc_iso
from realtykit.providers.base import FetchOutcome
from realtykit.settings import Settings, get_settings
from realtykit.store.facts import upsert_geos
from realtykit.store.government import upsert_government_areas
from realtykit.store.sources import upsert_source

SCC_CITY_LAYER = (
    "https://services2.arcgis.com/tcv2cMrq63AgvbHF/ArcGIS/rest/services/"
    "PlanningOfficeDataService2/FeatureServer/2"
)
SCC_PARCEL_LAYER = (
    "https://services2.arcgis.com/tcv2cMrq63AgvbHF/arcgis/rest/services/"
    "Parcels_Public_View/FeatureServer/0"
)
SMC_PARCEL_SERVICE = "https://gis.smcgov.org/maps/rest/services/ACRE/ACTIVE_PARCELS/FeatureServer"

TARGET_CITIES = (
    "PALO ALTO",
    "SANTA CLARA",
    "MOUNTAIN VIEW",
    "SUNNYVALE",
    "SAN JOSE",
)


def _query_url(base: str, params: dict[str, Any]) -> str:
    return f"{base}/query?{urlencode(params)}"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("error"):
        raise ValueError(f"ArcGIS error: {payload['error']}")
    return payload


def _observation_date(metadata: dict[str, Any]) -> str | None:
    millis = (metadata.get("editingInfo") or {}).get("lastEditDate")
    if millis:
        return datetime.fromtimestamp(float(millis) / 1000, UTC).date().isoformat()
    return None


def _freshness(observation_as_of: str | None) -> str:
    if not observation_as_of:
        return "unavailable"
    observed = datetime.fromisoformat(observation_as_of).date()
    age = (datetime.now(UTC).date() - observed).days
    return "fresh" if age <= 7 else "stale"


def _numbers(value: Any) -> Iterable[tuple[float, float]]:
    if not isinstance(value, list):
        return
    if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
        yield float(value[0]), float(value[1])
        return
    for item in value:
        yield from _numbers(item)


def _center(geometry: dict[str, Any]) -> tuple[float, float]:
    points = list(_numbers(geometry.get("coordinates")))
    if not points:
        raise ValueError("City boundary has no coordinates")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(ys) + max(ys)) / 2, (min(xs) + max(xs)) / 2


def _manifest_entry(fetch: CachedFetch, *, label: str, url: str) -> dict[str, Any]:
    return {
        "label": label,
        "url": url,
        "path": fetch.path.name,
        "fetched_at": fetch.fetched_at,
        "http_status": fetch.status_code,
        "etag": fetch.etag,
        "last_modified": fetch.last_modified,
        "sha256": fetch.content_sha256,
        "bytes": fetch.bytes,
        "from_cache": fetch.from_cache,
    }


def _outcome(
    *,
    source_id: str,
    dataset: str,
    url: str,
    fetched_at: str,
    status: str,
    note: str,
    observation_as_of: str | None = None,
    cached: CachedFetch | None = None,
    rows: int = 0,
) -> FetchOutcome:
    return FetchOutcome(
        source_id=source_id,
        provider="government",
        dataset=dataset,
        url=url,
        status=status,
        fetched_at=cached.fetched_at if cached else fetched_at,
        cadence="daily",
        observation_as_of=observation_as_of,
        http_last_modified=cached.last_modified if cached else None,
        etag=cached.etag if cached else None,
        content_sha256=cached.content_sha256 if cached else None,
        bytes=cached.bytes if cached else None,
        freshness=_freshness(observation_as_of) if status == "ok" else "unavailable",
        note=note,
        path=cached.path if cached else None,
        rows_upserted=rows,
    )


def ingest(
    conn: sqlite3.Connection, settings: Settings | None = None, force: bool = False
) -> list[FetchOutcome]:
    settings = settings or get_settings()
    snapshot = settings.government_snapshot_dir
    http = CachedHttp(settings, root=snapshot)
    fetched_at = utc_iso()
    manifest_files: list[dict[str, Any]] = []
    outcomes: list[FetchOutcome] = []
    area_rows: list[dict[str, Any]] = []

    parent = conn.execute(
        """
        SELECT geo_id FROM geos
        WHERE level = 'metro' AND lower(name) LIKE '%san jose%'
        ORDER BY CASE WHEN state = 'CA' THEN 0 ELSE 1 END
        LIMIT 1
        """
    ).fetchone()
    parent_geo_id = parent["geo_id"] if parent else None

    city_observation: str | None = None
    try:
        metadata_url = f"{SCC_CITY_LAYER}?f=pjson"
        metadata_fetch = http.get_cached(
            metadata_url, "santa-clara/city-limits.layer.json", force=force
        )
        manifest_files.append(
            _manifest_entry(
                metadata_fetch, label="Santa Clara city-limit metadata", url=metadata_url
            )
        )
        city_metadata = _read_json(metadata_fetch.path)
        city_observation = _observation_date(city_metadata)

        where = "NAME IN (" + ",".join(f"'{city}'" for city in TARGET_CITIES) + ")"
        geometry_url = _query_url(
            SCC_CITY_LAYER,
            {
                "where": where,
                "outFields": "NAME",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
            },
        )
        geometry_fetch = http.get_cached(
            geometry_url, "santa-clara/target-city-boundaries.geojson", force=force
        )
        manifest_files.append(
            _manifest_entry(geometry_fetch, label="Five target-city boundaries", url=geometry_url)
        )
        feature_collection = _read_json(geometry_fetch.path)
        city_parts: dict[str, list] = {city: [] for city in TARGET_CITIES}
        for feature in feature_collection.get("features") or []:
            properties = feature.get("properties") or {}
            upper_name = str(properties.get("NAME") or "").upper()
            if upper_name not in TARGET_CITIES:
                continue
            geometry = feature.get("geometry") or {}
            if geometry.get("type") == "Polygon":
                city_parts[upper_name].append(geometry.get("coordinates") or [])
            elif geometry.get("type") == "MultiPolygon":
                city_parts[upper_name].extend(geometry.get("coordinates") or [])

        for upper_name in TARGET_CITIES:
            if not city_parts[upper_name]:
                continue
            geometry = {"type": "MultiPolygon", "coordinates": city_parts[upper_name]}
            display_name = upper_name.title()
            slug = upper_name.lower().replace(" ", "-")
            lat, lon = _center(geometry)
            area_rows.append(
                {
                    "area_id": f"ca:scc:city:{slug}",
                    "name": display_name,
                    "state": "CA",
                    "county": "Santa Clara",
                    "parent_geo_id": parent_geo_id,
                    "provider": "government",
                    "source_id": "government:santa_clara_city_boundaries",
                    "lat": lat,
                    "lon": lon,
                    "parcel_count": None,
                    "geometry": geometry,
                    "observation_as_of": city_observation,
                    "fetched_at": geometry_fetch.fetched_at,
                    "note": "Official city boundary; market metrics use the San Jose metro aggregate.",
                }
            )
        outcomes.append(
            _outcome(
                source_id="government:santa_clara_city_boundaries",
                dataset="santa_clara_target_city_boundaries",
                url=SCC_CITY_LAYER,
                fetched_at=fetched_at,
                status="ok",
                note=f"Official boundaries for {len(area_rows)} target cities. No sale prices.",
                observation_as_of=city_observation,
                cached=geometry_fetch,
                rows=len(area_rows),
            )
        )
    except Exception as exc:  # noqa: BLE001
        outcomes.append(
            _outcome(
                source_id="government:santa_clara_city_boundaries",
                dataset="santa_clara_target_city_boundaries",
                url=SCC_CITY_LAYER,
                fetched_at=fetched_at,
                status="error",
                note=f"City-boundary refresh failed: {exc}",
            )
        )

    parcel_observation: str | None = None
    parcel_cached: CachedFetch | None = None
    counts: dict[str, int] = {}
    try:
        metadata_url = f"{SCC_PARCEL_LAYER}?f=pjson"
        parcel_cached = http.get_cached(metadata_url, "santa-clara/parcels.layer.json", force=force)
        manifest_files.append(
            _manifest_entry(
                parcel_cached, label="Santa Clara public-parcel metadata", url=metadata_url
            )
        )
        parcel_metadata = _read_json(parcel_cached.path)
        parcel_observation = _observation_date(parcel_metadata)
        for city in TARGET_CITIES:
            count_url = _query_url(
                SCC_PARCEL_LAYER,
                {
                    "where": f"Situs_Address_Full LIKE '% {city} CA %'",
                    "returnCountOnly": "true",
                    "f": "json",
                },
            )
            count_fetch = http.get_cached(
                count_url,
                f"santa-clara/parcel-counts/{city.lower().replace(' ', '-')}.json",
                force=force,
            )
            manifest_files.append(
                _manifest_entry(count_fetch, label=f"{city.title()} parcel count", url=count_url)
            )
            count_payload = _read_json(count_fetch.path)
            counts[city.title()] = int(count_payload.get("count") or 0)

        for area in area_rows:
            area["parcel_count"] = counts.get(area["name"])
            area["note"] = (
                "Official boundary with an address-derived public parcel count; "
                "the parcel layer does not publish sale consideration."
            )
        outcomes.append(
            _outcome(
                source_id="government:santa_clara_parcels",
                dataset="santa_clara_public_parcel_index",
                url=SCC_PARCEL_LAYER,
                fetched_at=fetched_at,
                status="ok",
                note=(
                    f"Address-derived parcel counts for {len(counts)} target cities "
                    f"({sum(counts.values()):,} records). No sale-price field."
                ),
                observation_as_of=parcel_observation,
                cached=parcel_cached,
                rows=len(counts),
            )
        )
    except Exception as exc:  # noqa: BLE001
        outcomes.append(
            _outcome(
                source_id="government:santa_clara_parcels",
                dataset="santa_clara_public_parcel_index",
                url=SCC_PARCEL_LAYER,
                fetched_at=fetched_at,
                status="error",
                note=f"Parcel metadata/count refresh failed: {exc}",
                observation_as_of=parcel_observation,
                cached=parcel_cached,
            )
        )

    if area_rows:
        upsert_government_areas(area_rows, conn)
        upsert_geos(
            [
                {
                    "geo_id": area["area_id"],
                    "level": "city",
                    "name": area["name"],
                    "state": area["state"],
                    "parent_geo_id": area["parent_geo_id"],
                    "lat": area["lat"],
                    "lon": area["lon"],
                }
                for area in area_rows
            ],
            conn,
        )

    try:
        metadata_url = f"{SMC_PARCEL_SERVICE}?f=pjson"
        smc_cached = http.get_cached(
            metadata_url, "san-mateo/active-parcels.service.json", force=force
        )
        manifest_files.append(
            _manifest_entry(
                smc_cached, label="San Mateo active-parcel service metadata", url=metadata_url
            )
        )
        smc_metadata = _read_json(smc_cached.path)
        smc_observation = _observation_date(smc_metadata)
        outcomes.append(
            _outcome(
                source_id="government:san_mateo_parcels",
                dataset="san_mateo_active_parcel_service",
                url=SMC_PARCEL_SERVICE,
                fetched_at=fetched_at,
                status="ok",
                note="Adjacent county reference source. It does not cover the five Santa Clara target cities or publish sale prices.",
                observation_as_of=smc_observation,
                cached=smc_cached,
            )
        )
    except Exception as exc:  # noqa: BLE001
        outcomes.append(
            _outcome(
                source_id="government:san_mateo_parcels",
                dataset="san_mateo_active_parcel_service",
                url=SMC_PARCEL_SERVICE,
                fetched_at=fetched_at,
                status="error",
                note=f"San Mateo metadata refresh failed: {exc}",
            )
        )

    for outcome in outcomes:
        upsert_source(outcome.as_source_row(), conn)

    manifest = {
        "snapshot_date_utc": snapshot.name,
        "created_at": utc_iso(),
        "scope": {
            "primary_county": "Santa Clara County, California",
            "target_cities": [city.title() for city in TARGET_CITIES],
            "adjacent_reference": "San Mateo County, California",
        },
        "limitations": [
            "These are geography and parcel-reference sources, not deed sale-price feeds.",
            "Santa Clara parcel counts are derived from the situs-address city text.",
            "Full parcel polygons are intentionally not bulk-downloaded; use an on-demand bounded query.",
        ],
        "files": manifest_files,
    }
    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return outcomes
