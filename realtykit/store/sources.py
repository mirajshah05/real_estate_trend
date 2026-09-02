from __future__ import annotations

import sqlite3
from typing import Any

from realtykit.store.db import connect


def upsert_source(row: dict[str, Any], conn: sqlite3.Connection | None = None) -> None:
    owned = conn is None
    conn = conn or connect()
    conn.execute(
        """
        INSERT INTO sources (
          source_id, provider, dataset, url, http_last_modified, etag,
          content_sha256, bytes, fetched_at, observation_as_of, cadence, freshness, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
          provider=excluded.provider,
          dataset=excluded.dataset,
          url=excluded.url,
          http_last_modified=excluded.http_last_modified,
          etag=excluded.etag,
          content_sha256=excluded.content_sha256,
          bytes=excluded.bytes,
          fetched_at=excluded.fetched_at,
          observation_as_of=excluded.observation_as_of,
          cadence=excluded.cadence,
          freshness=excluded.freshness,
          note=excluded.note
        """,
        (
            row["source_id"],
            row["provider"],
            row.get("dataset") or "",
            row.get("url") or "",
            row.get("http_last_modified"),
            row.get("etag"),
            row.get("content_sha256"),
            row.get("bytes"),
            row["fetched_at"],
            row.get("observation_as_of"),
            row.get("cadence") or "unknown",
            row.get("freshness") or "unavailable",
            row.get("note") or "",
        ),
    )
    if owned:
        conn.commit()
        conn.close()


def list_sources(conn: sqlite3.Connection | None = None) -> list[dict]:
    owned = conn is None
    conn = conn or connect()
    rows = [dict(r) for r in conn.execute("SELECT * FROM sources ORDER BY provider, dataset")]
    if owned:
        conn.close()
    return rows


def get_source(source_id: str, conn: sqlite3.Connection | None = None) -> dict | None:
    owned = conn is None
    conn = conn or connect()
    row = conn.execute("SELECT * FROM sources WHERE source_id = ?", (source_id,)).fetchone()
    if owned:
        conn.close()
    return dict(row) if row else None
