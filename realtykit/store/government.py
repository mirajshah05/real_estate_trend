from __future__ import annotations

import json
import sqlite3
from typing import Any

from realtykit.store.db import connect


def upsert_government_areas(
    rows: list[dict[str, Any]], conn: sqlite3.Connection | None = None
) -> int:
    owned = conn is None
    conn = conn or connect()
    conn.executemany(
        """
        INSERT INTO government_areas (
          area_id, name, state, county, parent_geo_id, provider, source_id,
          lat, lon, parcel_count, geometry_geojson, observation_as_of, fetched_at, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(area_id) DO UPDATE SET
          name=excluded.name,
          state=excluded.state,
          county=excluded.county,
          parent_geo_id=excluded.parent_geo_id,
          provider=excluded.provider,
          source_id=excluded.source_id,
          lat=excluded.lat,
          lon=excluded.lon,
          parcel_count=excluded.parcel_count,
          geometry_geojson=excluded.geometry_geojson,
          observation_as_of=excluded.observation_as_of,
          fetched_at=excluded.fetched_at,
          note=excluded.note
        """,
        [
            (
                row["area_id"], row["name"], row["state"], row["county"],
                row.get("parent_geo_id"), row["provider"], row["source_id"],
                row["lat"], row["lon"], row.get("parcel_count"),
                json.dumps(row["geometry"], separators=(",", ":")),
                row.get("observation_as_of"), row["fetched_at"], row.get("note"),
            )
            for row in rows
        ],
    )
    if owned:
        conn.commit()
        conn.close()
    return len(rows)


def list_government_areas(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    owned = conn is None
    conn = conn or connect()
    rows = [dict(row) for row in conn.execute(
        "SELECT * FROM government_areas ORDER BY state, county, name"
    ).fetchall()]
    if owned:
        conn.close()
    for row in rows:
        row["geometry"] = json.loads(row.pop("geometry_geojson"))
    return rows
