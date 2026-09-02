from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Any

from realtykit.store.db import connect

_CHUNK = 5000


def _chunks(rows: list[tuple], size: int = _CHUNK) -> Iterable[list[tuple]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def upsert_geos(rows: list[dict[str, Any]], conn: sqlite3.Connection | None = None) -> int:
    owned = conn is None
    conn = conn or connect()
    tuples = [
        (
            r["geo_id"],
            r.get("level") or "metro",
            r["name"],
            r.get("state"),
            r.get("parent_geo_id"),
            r.get("lat"),
            r.get("lon"),
            r.get("population"),
        )
        for r in rows
    ]
    conn.executemany(
        """
        INSERT INTO geos (geo_id, level, name, state, parent_geo_id, lat, lon, population)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(geo_id) DO UPDATE SET
          level=excluded.level,
          name=excluded.name,
          state=COALESCE(excluded.state, geos.state),
          parent_geo_id=COALESCE(excluded.parent_geo_id, geos.parent_geo_id),
          lat=COALESCE(excluded.lat, geos.lat),
          lon=COALESCE(excluded.lon, geos.lon),
          population=COALESCE(excluded.population, geos.population)
        """,
        tuples,
    )
    if owned:
        conn.commit()
        conn.close()
    return len(tuples)


def upsert_facts(rows: list[dict[str, Any]], conn: sqlite3.Connection | None = None) -> int:
    owned = conn is None
    conn = conn or connect()
    tuples = [
        (
            r["geo_id"],
            r.get("period_start"),
            r["period_end"],
            r.get("cadence") or "weekly",
            r["metric"],
            r.get("value"),
            r["provider"],
            r["source_id"],
        )
        for r in rows
    ]
    sql = """
        INSERT INTO market_facts (
          geo_id, period_start, period_end, cadence, metric, value, provider, source_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(geo_id, period_end, metric, provider) DO UPDATE SET
          value=excluded.value,
          period_start=excluded.period_start,
          cadence=excluded.cadence,
          source_id=excluded.source_id
    """
    for chunk in _chunks(tuples):
        conn.executemany(sql, chunk)
    if owned:
        conn.commit()
        conn.close()
    return len(tuples)


def upsert_macro(rows: list[dict[str, Any]], conn: sqlite3.Connection | None = None) -> int:
    owned = conn is None
    conn = conn or connect()
    tuples = [(r["series_id"], r["ts"], r["value"], r["provider"], r["source_id"]) for r in rows]
    conn.executemany(
        """
        INSERT INTO macro_series (series_id, ts, value, provider, source_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(series_id, ts) DO UPDATE SET
          value=excluded.value,
          provider=excluded.provider,
          source_id=excluded.source_id
        """,
        tuples,
    )
    if owned:
        conn.commit()
        conn.close()
    return len(tuples)


def latest_period(
    metric: str, geo_id: str | None = None, conn: sqlite3.Connection | None = None
) -> str | None:
    owned = conn is None
    conn = conn or connect()
    if geo_id:
        row = conn.execute(
            "SELECT MAX(period_end) AS p FROM market_facts WHERE metric = ? AND geo_id = ?",
            (metric, geo_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT MAX(period_end) AS p FROM market_facts WHERE metric = ?",
            (metric,),
        ).fetchone()
    if owned:
        conn.close()
    return row["p"] if row else None


def latest_facts(
    metric: str,
    *,
    period_end: str | None = None,
    geo_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    owned = conn is None
    conn = conn or connect()
    period = period_end or latest_period(metric, geo_id, conn)
    if not period:
        if owned:
            conn.close()
        return []
    if geo_id:
        rows = conn.execute(
            """
            SELECT f.*, g.name, g.state, g.lat, g.lon, g.level
            FROM market_facts f
            LEFT JOIN geos g ON g.geo_id = f.geo_id
            WHERE f.metric = ? AND f.period_end = ? AND f.geo_id = ?
            """,
            (metric, period, geo_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT f.*, g.name, g.state, g.lat, g.lon, g.level
            FROM market_facts f
            LEFT JOIN geos g ON g.geo_id = f.geo_id
            WHERE f.metric = ? AND f.period_end = ?
            """,
            (metric, period),
        ).fetchall()
    if owned:
        conn.close()
    return [dict(r) for r in rows]


def series_for(
    geo_id: str,
    metric: str,
    *,
    limit: int = 260,
    provider: str | None = None,
    cadence: str | None = None,
    from_period: str | None = None,
    to_period: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[tuple[str, float]]:
    owned = conn is None
    conn = conn or connect()
    clauses = ["geo_id = ?", "metric = ?", "value IS NOT NULL"]
    params: list[object] = [geo_id, metric]
    if provider:
        clauses.append("provider = ?")
        params.append(provider)
    if cadence:
        clauses.append("cadence = ?")
        params.append(cadence)
    if from_period:
        clauses.append("period_end >= ?")
        params.append(from_period)
    if to_period:
        clauses.append("period_end <= ?")
        params.append(to_period)
    rows = conn.execute(
        f"SELECT period_end, value FROM market_facts WHERE {' AND '.join(clauses)} ORDER BY period_end",
        params,
    ).fetchall()
    if owned:
        conn.close()
    pts = [(r["period_end"], float(r["value"])) for r in rows]
    return pts[-limit:]


def macro_series(
    series_id: str,
    conn: sqlite3.Connection | None = None,
    *,
    limit: int | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> list[tuple[str, float]]:
    owned = conn is None
    conn = conn or connect()
    clauses = ["series_id = ?"]
    params: list[object] = [series_id]
    if from_ts:
        clauses.append("ts >= ?")
        params.append(from_ts)
    if to_ts:
        clauses.append("ts <= ?")
        params.append(to_ts)
    sql = f"SELECT ts, value FROM macro_series WHERE {' AND '.join(clauses)} ORDER BY ts"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    if owned:
        conn.close()
    return [(r["ts"], float(r["value"])) for r in rows]


def get_geo(geo_id: str, conn: sqlite3.Connection | None = None) -> dict | None:
    owned = conn is None
    conn = conn or connect()
    row = conn.execute("SELECT * FROM geos WHERE geo_id = ?", (geo_id,)).fetchone()
    if owned:
        conn.close()
    return dict(row) if row else None


def resolve_geo(value: str | None, conn: sqlite3.Connection | None = None) -> str:
    """Accept geo_id, US, or a metro name fragment."""
    if not value or value.upper() in {"US", "USA", "NATION:US", "UNITED STATES"}:
        return "nation:US"
    owned = conn is None
    conn = conn or connect()
    row = conn.execute("SELECT geo_id FROM geos WHERE geo_id = ?", (value,)).fetchone()
    if row:
        if owned:
            conn.close()
        return row["geo_id"]
    row = conn.execute(
        "SELECT geo_id FROM geos WHERE lower(name) = lower(?) LIMIT 1",
        (value,),
    ).fetchone()
    if owned:
        conn.close()
    return row["geo_id"] if row else value


def fact_count(conn: sqlite3.Connection | None = None) -> int:
    owned = conn is None
    conn = conn or connect()
    n = conn.execute("SELECT COUNT(*) AS n FROM market_facts").fetchone()["n"]
    if owned:
        conn.close()
    return int(n)
