"""Sanitized property sale-event persistence (owner data is never stored)."""

from __future__ import annotations

import sqlite3


def upsert_sales(rows: list[dict], conn: sqlite3.Connection) -> int:
    conn.executemany(
        """
        INSERT INTO sale_events (
          event_id, provider, property_id, address, city, state, zip_code,
          lat, lon, sale_date, price, property_type, beds, baths, sqft, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
          address=excluded.address, city=excluded.city, state=excluded.state,
          zip_code=excluded.zip_code, lat=excluded.lat, lon=excluded.lon,
          sale_date=excluded.sale_date, price=excluded.price,
          property_type=excluded.property_type, beds=excluded.beds,
          baths=excluded.baths, sqft=excluded.sqft, fetched_at=excluded.fetched_at
        """,
        [
            (
                row["event_id"],
                row["provider"],
                row["property_id"],
                row.get("address"),
                row.get("city"),
                row.get("state"),
                row.get("zip_code"),
                row["lat"],
                row["lon"],
                row["sale_date"],
                row.get("price"),
                row.get("property_type"),
                row.get("beds"),
                row.get("baths"),
                row.get("sqft"),
                row["fetched_at"],
            )
            for row in rows
        ],
    )
    return len(rows)
