"""Persistence and aggregate queries for user-imported rental observations."""

from __future__ import annotations

import json
import sqlite3
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

from realtykit.models.rental import RentalObservation


class RentalIdentityConflict(ValueError):
    """A source observation ID was reused for a different event."""

    def __init__(self, observation_id: str):
        self.observation_id = observation_id
        super().__init__(
            f"observation_id '{observation_id}' already identifies a different source, city, or date"
        )


def prune_rental_observations(conn: sqlite3.Connection, *, before: date) -> int:
    cursor = conn.execute(
        "DELETE FROM rental_observations WHERE observed_on < ?",
        (before.isoformat(),),
    )
    return max(0, cursor.rowcount)


def upsert_rental_observations(
    observations: list[RentalObservation],
    *,
    import_id: str,
    imported_at: str,
    conn: sqlite3.Connection,
) -> tuple[int, int]:
    """Upsert validated observations, returning ``(inserted, updated)``."""
    identifiers = [row.observation_id for row in observations if row.observation_id]
    existing: dict[str, tuple[str, str, str]] = {}
    for offset in range(0, len(identifiers), 500):
        batch = identifiers[offset : offset + 500]
        marks = ",".join("?" for _ in batch)
        stored = conn.execute(
            f"SELECT observation_id, source, observed_on, city FROM rental_observations "
            f"WHERE observation_id IN ({marks})",
            batch,
        ).fetchall()
        existing.update(
            {
                str(row["observation_id"]): (
                    str(row["source"]),
                    str(row["observed_on"]),
                    str(row["city"]),
                )
                for row in stored
            }
        )

    for row in observations:
        identity = existing.get(str(row.observation_id))
        proposed = (row.source, row.observed_on.isoformat(), row.city)
        if identity is not None and identity != proposed:
            raise RentalIdentityConflict(str(row.observation_id))

    conn.executemany(
        """
        INSERT INTO rental_observations (
          observation_id, import_id, source, observed_on, city, zip_code,
          neighborhood, monthly_rent, bedrooms, bathrooms, property_type,
          listing_status, availability_status, sqft, year_built, amenities_json,
          latitude, longitude, removed_on, last_seen_on, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(observation_id) DO UPDATE SET
          import_id=excluded.import_id,
          source=excluded.source,
          observed_on=excluded.observed_on,
          city=excluded.city,
          zip_code=excluded.zip_code,
          neighborhood=excluded.neighborhood,
          monthly_rent=excluded.monthly_rent,
          bedrooms=excluded.bedrooms,
          bathrooms=excluded.bathrooms,
          property_type=excluded.property_type,
          listing_status=excluded.listing_status,
          availability_status=excluded.availability_status,
          sqft=excluded.sqft,
          year_built=excluded.year_built,
          amenities_json=excluded.amenities_json,
          latitude=excluded.latitude,
          longitude=excluded.longitude,
          removed_on=excluded.removed_on,
          last_seen_on=excluded.last_seen_on,
          imported_at=excluded.imported_at
        """,
        [
            (
                row.observation_id,
                import_id,
                row.source,
                row.observed_on.isoformat(),
                row.city,
                row.zip_code,
                row.neighborhood,
                row.monthly_rent,
                row.bedrooms,
                row.bathrooms,
                row.property_type,
                row.listing_status,
                row.availability_status,
                row.sqft,
                row.year_built,
                json.dumps(row.amenities, separators=(",", ":")),
                row.latitude,
                row.longitude,
                row.removed_on.isoformat() if row.removed_on else None,
                row.last_seen_on.isoformat() if row.last_seen_on else None,
                imported_at,
            )
            for row in observations
        ],
    )
    updated = sum(1 for identifier in identifiers if identifier in existing)
    return len(observations) - updated, updated


def record_rental_import(
    *,
    import_id: str,
    filename: str,
    file_format: str,
    content_sha256: str,
    row_count: int,
    inserted: int,
    updated: int,
    imported_at: str,
    conn: sqlite3.Connection,
) -> None:
    conn.execute(
        """
        INSERT INTO rental_imports (
          import_id, filename, file_format, content_sha256, row_count,
          inserted, updated, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(import_id) DO UPDATE SET
          filename=excluded.filename,
          row_count=excluded.row_count,
          inserted=excluded.inserted,
          updated=excluded.updated,
          imported_at=excluded.imported_at
        """,
        (
            import_id,
            filename,
            file_format,
            content_sha256,
            row_count,
            inserted,
            updated,
            imported_at,
        ),
    )


def _month_start(value: date, months_back: int) -> date:
    index = value.year * 12 + value.month - 1 - months_back
    return date(index // 12, index % 12 + 1, 1)


def rental_trends(
    conn: sqlite3.Connection,
    *,
    city: str,
    months: int = 12,
    as_of: date | None = None,
    bedrooms: int | None = None,
    property_type: str | None = None,
    listing_status: str | None = None,
    availability_status: str | None = None,
) -> dict[str, Any]:
    """Return exact monthly aggregates for every requested market segment."""
    market_as_of = as_of
    where = ["city = ?"]
    params: list[Any] = [city]
    if bedrooms is not None:
        where.append("bedrooms = ?")
        params.append(bedrooms)
    if property_type is not None:
        where.append("property_type = ?")
        params.append(property_type)
    if listing_status is not None:
        where.append("listing_status = ?")
        params.append(listing_status)
    if availability_status is not None:
        where.append("availability_status = ?")
        params.append(availability_status)

    if as_of is None:
        row = conn.execute(
            f"SELECT MAX(observed_on) AS observed_on FROM rental_observations "
            f"WHERE {' AND '.join(where)}",
            params,
        ).fetchone()
        as_of = (
            date.fromisoformat(row["observed_on"])
            if row and row["observed_on"]
            else datetime.now(UTC).date()
        )

    date_from = _month_start(as_of, months - 1)
    where.extend(["observed_on >= ?", "observed_on <= ?"])
    params.extend([date_from.isoformat(), as_of.isoformat()])
    rows = conn.execute(
        f"""
        SELECT observed_on, monthly_rent, bedrooms, property_type, listing_status,
               availability_status
        FROM rental_observations
        WHERE {' AND '.join(where)}
        ORDER BY observed_on, bedrooms, property_type, listing_status
        """,
        params,
    ).fetchall()

    groups: dict[tuple[str, int, str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["observed_on"])[:7],
            int(row["bedrooms"]),
            str(row["property_type"]),
            str(row["listing_status"]),
            str(row["availability_status"]),
        )
        groups[key].append(float(row["monthly_rent"]))

    points = []
    for key in sorted(groups):
        values = groups[key]
        points.append(
            {
                "month": key[0],
                "bedrooms": key[1],
                "property_type": key[2],
                "listing_status": key[3],
                "availability_status": key[4],
                "count": len(values),
                "median_rent": round(statistics.median(values), 2),
                "average_rent": round(statistics.fmean(values), 2),
                "min_rent": round(min(values), 2),
                "max_rent": round(max(values), 2),
            }
        )
    observed_dates = [str(row["observed_on"]) for row in rows]
    market_indices = rental_market_indices(
        conn,
        city=city,
        months=months,
        as_of=market_as_of,
    )
    return {
        "city": city,
        "months": months,
        "date_from": date_from.isoformat(),
        "date_to": as_of.isoformat(),
        "observation_count": len(rows),
        "first_observed_on": min(observed_dates) if observed_dates else None,
        "last_observed_on": max(observed_dates) if observed_dates else None,
        "segments": points,
        "market_indices": market_indices,
    }


def rental_market_indices(
    conn: sqlite3.Connection,
    *,
    city: str,
    months: int,
    as_of: date | None,
) -> list[dict[str, Any]]:
    """Return aggregate rental indices without implying property-level cuts."""
    if as_of is None:
        latest = conn.execute(
            """
            SELECT MAX(f.period_end) AS period_end
            FROM market_facts f JOIN geos g ON g.geo_id = f.geo_id
            WHERE g.name = ? AND g.state = 'CA' AND f.metric = 'zori_all'
            """,
            (city,),
        ).fetchone()
        if not latest or not latest["period_end"]:
            return []
        as_of = date.fromisoformat(str(latest["period_end"])[:10])
    date_from = _month_start(as_of, months - 1).isoformat()
    rows = conn.execute(
        """
        SELECT f.period_end, f.value, f.provider, f.source_id
        FROM market_facts f
        JOIN geos g ON g.geo_id = f.geo_id
        WHERE g.name = ? AND g.state = 'CA'
          AND f.metric = 'zori_all'
          AND f.period_end >= ? AND f.period_end <= ?
        ORDER BY f.period_end
        """,
        (city, date_from, as_of.isoformat()),
    ).fetchall()
    if not rows:
        return []
    return [
        {
            "provider": str(rows[0]["provider"]),
            "source_id": str(rows[0]["source_id"]),
            "metric": "zori",
            "home_type": "all_homes",
            "city": city,
            "as_of": str(rows[-1]["period_end"]),
            "points": [
                {"month": str(row["period_end"])[:7], "value": round(float(row["value"]), 2)}
                for row in rows
            ],
        }
    ]


def list_rental_observations(
    conn: sqlite3.Connection,
    *,
    city: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    where = "WHERE city = ?" if city else ""
    params: list[Any] = [city] if city else []
    total = int(
        conn.execute(
            f"SELECT COUNT(*) AS n FROM rental_observations {where}", params
        ).fetchone()["n"]
    )
    rows = conn.execute(
        f"""
        SELECT observation_id, import_id, source, observed_on, city, zip_code,
               neighborhood, monthly_rent, bedrooms, bathrooms, property_type,
               listing_status, availability_status, sqft, year_built, amenities_json,
               latitude, longitude, removed_on, last_seen_on, imported_at
        FROM rental_observations {where}
        ORDER BY observed_on DESC, observation_id
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        try:
            amenities = json.loads(item.pop("amenities_json") or "[]")
            item["amenities"] = (
                [value for value in amenities if isinstance(value, str)]
                if isinstance(amenities, list)
                else []
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            item["amenities"] = []
        results.append(item)
    return results, total
