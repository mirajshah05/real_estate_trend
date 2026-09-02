"""Compass has no public listings API. Always unavailable. Do not scrape."""

from __future__ import annotations

import sqlite3

from realtykit.log import utc_iso
from realtykit.providers.base import FetchOutcome
from realtykit.store.sources import upsert_source


def ingest(conn: sqlite3.Connection, **_kwargs) -> FetchOutcome:
    out = FetchOutcome(
        source_id="compass:listings",
        provider="compass",
        dataset="listings",
        url="",
        status="unavailable",
        fetched_at=utc_iso(),
        cadence="unknown",
        freshness="unavailable",
        note="No official Compass API. Adapter always returns unavailable. Not scraped.",
    )
    upsert_source(out.as_source_row(), conn)
    return out


def status_payload() -> dict:
    return {"status": "unavailable", "provider": "compass"}
