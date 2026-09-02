from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from realtykit.api.deps import ensure_store
from realtykit.api.schemas import SearchResponse, SearchResult
from realtykit.freshness import build_freshness
from realtykit.providers.census_geocoder import geocode
from realtykit.store.db import connect

router = APIRouter()


def _like(value: str) -> str:
    """Escape SQL LIKE wildcards while keeping the query parameterized."""
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _nearest_metro(lat: float, lon: float, conn) -> dict | None:
    rows = conn.execute(
        "SELECT geo_id, name, state, lat, lon FROM geos "
        "WHERE level = 'metro' AND lat IS NOT NULL AND lon IS NOT NULL"
    ).fetchall()
    if not rows:
        return None
    return min(
        (dict(row) for row in rows),
        key=lambda row: (float(row["lat"]) - lat) ** 2 + (float(row["lon"]) - lon) ** 2,
    )


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(min_length=2, max_length=160),
    _ok: None = Depends(ensure_store),
) -> SearchResponse:
    query = q.strip()
    if not query:
        return SearchResponse(
            freshness=build_freshness(), query=q, note="Enter a city, ZIP code, or address."
        )

    conn = connect()
    try:
        pattern = _like(query.lower())
        rows = conn.execute(
            """
            SELECT
              CASE WHEN g.level = 'zip' AND g.geo_id LIKE 'zillow:zip:%'
                   THEN g.geo_id ELSE g.geo_id END AS geo_id,
              g.name, g.state,
              COALESCE(g.lat, c.lat) AS lat,
              COALESCE(g.lon, c.lon) AS lon,
              g.level,
              CASE WHEN g.level = 'zip' AND g.geo_id LIKE 'zillow:zip:%'
                   THEN g.geo_id
                   WHEN g.level = 'city' THEN g.parent_geo_id
                   ELSE NULL END AS market_geo_id
            FROM geos g
            LEFT JOIN geos c ON c.geo_id = 'census:zcta:' || g.name
            WHERE lower(g.name || ' ' || COALESCE(g.state, '') || ' ' || g.geo_id)
                  LIKE ? ESCAPE '\\'
              AND (
                g.geo_id NOT LIKE 'census:zcta:%'
                OR NOT EXISTS (
                  SELECT 1 FROM geos z WHERE z.geo_id = 'zillow:zip:' || g.name
                )
              )
            ORDER BY CASE WHEN lower(g.name) = lower(?) THEN 0 ELSE 1 END,
                     CASE g.level WHEN 'metro' THEN 0 WHEN 'city' THEN 1 WHEN 'zip' THEN 2 ELSE 3 END,
                     g.name
            LIMIT 12
            """,
            (pattern, query),
        ).fetchall()
        results = []
        for row in rows:
            if row["lat"] is None or row["lon"] is None:
                continue
            market_geo_id = row["market_geo_id"]
            if row["level"] == "zip" and not market_geo_id:
                metro = _nearest_metro(float(row["lat"]), float(row["lon"]), conn)
                market_geo_id = metro["geo_id"] if metro else None
            results.append(
                SearchResult(
                    geo_id=row["geo_id"],
                    name=row["name"],
                    state=row["state"],
                    lat=row["lat"],
                    lon=row["lon"],
                    kind=row["level"],
                    label=f"{row['name']}{', ' + row['state'] if row['state'] else ''}",
                    market_geo_id=market_geo_id,
                )
            )

        # The Census geocoder handles full US street addresses without an API key.
        # Avoid sending ordinary city/ZIP searches to a remote service.
        looks_like_address = any(ch.isdigit() for ch in query) and len(results) == 0
        if looks_like_address:
            for match in geocode(query):
                metro = _nearest_metro(match["lat"], match["lon"], conn)
                if not metro:
                    continue
                results.append(
                    SearchResult(
                        geo_id=metro["geo_id"],
                        name=metro["name"],
                        state=metro["state"],
                        lat=match["lat"],
                        lon=match["lon"],
                        kind="address",
                        label=match["label"],
                        market_geo_id=metro["geo_id"],
                    )
                )
    finally:
        conn.close()

    note = "" if results else "No matching metro, city, ZIP, or US address was found."
    if any(result.kind == "address" for result in results):
        note = "Address centered by the Census Geocoder; market metrics are shown for the nearest tracked metro."
    elif any(result.kind == "city" and result.market_geo_id for result in results):
        note = "Official city boundary selected; market metrics are shown for its tracked parent metro."
    return SearchResponse(
        freshness=build_freshness(prefer_source="census:zcta_2024"),
        query=query,
        results=results,
        note=note,
    )
