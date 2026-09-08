"""Explicit, bounded provider collection for target-city rental research."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from realtykit.ingest.rentals import import_rentals
from realtykit.log import utc_iso
from realtykit.providers import rentcast
from realtykit.providers.base import FetchOutcome
from realtykit.settings import Settings, get_settings
from realtykit.store.sources import upsert_source


def collect_rentcast(
    conn: sqlite3.Connection,
    *,
    settings: Settings | None = None,
    cities: tuple[str, ...] = rentcast.TARGET_RENTAL_CITIES,
    statuses: tuple[str, ...] = ("active", "inactive"),
    limit_per_query: int = 100,
    days_old: int = 1095,
    force: bool = False,
) -> dict[str, Any]:
    """Collect at most one provider page for each requested city/status pair."""
    settings = settings or get_settings()
    fetched_at = utc_iso()
    if not settings.has_rentcast_key:
        outcome = FetchOutcome(
            source_id="rentcast:rental_long_term",
            provider="rentcast",
            dataset="target_city_long_term_rentals",
            url=rentcast.RENTAL_URL,
            status="skipped",
            fetched_at=fetched_at,
            cadence="daily",
            freshness="unavailable",
            note="Skipped — RENTCAST_API_KEY not set.",
        )
        upsert_source(outcome.as_source_row(), conn)
        conn.commit()
        return {"provider": "rentcast", "status": "skipped", "queries": [], "rows": 0}

    if not 1 <= limit_per_query <= 500 or not 1 <= days_old <= 1095:
        raise ValueError("limit_per_query must be 1-500 and days_old must be 1-1095")
    invalid_cities = sorted(set(cities) - set(rentcast.TARGET_RENTAL_CITIES))
    invalid_statuses = sorted(set(statuses) - {"active", "inactive"})
    if invalid_cities or invalid_statuses:
        raise ValueError("collection scope contains an unsupported city or status")

    summaries: list[dict[str, Any]] = []
    inserted = 0
    updated = 0
    latest_observation: str | None = None
    for city in cities:
        for status in statuses:
            try:
                rows, cached = rentcast.fetch_city_rentals(
                    city=city,
                    status=status,
                    days_old=days_old,
                    limit=limit_per_query,
                    settings=settings,
                    force=force,
                )
            except Exception as exc:
                outcome = FetchOutcome(
                    source_id="rentcast:rental_long_term",
                    provider="rentcast",
                    dataset="target_city_long_term_rentals",
                    url=rentcast.RENTAL_URL,
                    status="error",
                    fetched_at=fetched_at,
                    cadence="daily",
                    freshness="unavailable",
                    note=f"Collection stopped at {city}/{status}: {type(exc).__name__}.",
                )
                upsert_source(outcome.as_source_row(), conn)
                conn.commit()
                raise
            result = None
            if rows:
                content = json.dumps(rows, sort_keys=True, separators=(",", ":"))
                result = import_rentals(
                    filename=f"rentcast-{city.lower().replace(' ', '-')}-{status}.json",
                    file_format="json",
                    content=content,
                    conn=conn,
                )
                inserted += result["inserted"]
                updated += result["updated"]
                latest_observation = max(latest_observation or "", result["date_max"])
            summaries.append(
                {
                    "city": city,
                    "availability_status": status,
                    "cached": cached,
                    "rows": len(rows),
                    "inserted": result["inserted"] if result else 0,
                    "updated": result["updated"] if result else 0,
                }
            )

    total = inserted + updated
    outcome = FetchOutcome(
        source_id="rentcast:rental_long_term",
        provider="rentcast",
        dataset="target_city_long_term_rentals",
        url=rentcast.RENTAL_URL,
        status="ok",
        fetched_at=fetched_at,
        cadence="daily",
        observation_as_of=latest_observation,
        freshness="fresh" if latest_observation else "unavailable",
        rows_upserted=total,
        note=(
            f"Sanitized one-page city/status collection; {len(summaries)} bounded queries, "
            f"at most {limit_per_query} provider records each. Contacts and MLS metadata discarded."
        ),
    )
    upsert_source(outcome.as_source_row(), conn)
    conn.commit()
    return {
        "provider": "rentcast",
        "status": "ok",
        "queries": summaries,
        "rows": total,
        "inserted": inserted,
        "updated": updated,
        "observation_as_of": latest_observation,
    }
