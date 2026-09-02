from __future__ import annotations

import sqlite3


def upsert_listings(rows: list[dict], conn: sqlite3.Connection) -> int:
    """Persist the small, viewport-scoped listing slice used by outlier analysis."""
    conn.executemany(
        """
        INSERT INTO listings (
          listing_id, provider, geo_id, lat, lon, price, beds, baths, sqft,
          dom, status, listed_at, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(listing_id) DO UPDATE SET
          provider=excluded.provider,
          geo_id=excluded.geo_id,
          lat=excluded.lat,
          lon=excluded.lon,
          price=excluded.price,
          beds=excluded.beds,
          baths=excluded.baths,
          sqft=excluded.sqft,
          dom=excluded.dom,
          status=excluded.status,
          listed_at=excluded.listed_at,
          fetched_at=excluded.fetched_at
        """,
        [
            (
                row["listing_id"], row["provider"], row.get("geo_id"), row["lat"], row["lon"],
                row.get("price"), row.get("beds"), row.get("baths"), row.get("sqft"),
                row.get("dom"), row.get("status") or "active", row.get("listed_at"),
                row.get("fetched_at"),
            )
            for row in rows
        ],
    )
    return len(rows)
