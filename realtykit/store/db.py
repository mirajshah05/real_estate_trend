"""SQLite serving store. Parameterized SQL only. API never reads raw dumps."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from realtykit.settings import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  source_id            TEXT PRIMARY KEY,
  provider             TEXT NOT NULL,
  dataset              TEXT NOT NULL,
  url                  TEXT NOT NULL,
  http_last_modified   TEXT,
  etag                 TEXT,
  content_sha256       TEXT,
  bytes                INTEGER,
  fetched_at           TEXT NOT NULL,
  observation_as_of    TEXT,
  cadence              TEXT NOT NULL,
  freshness            TEXT NOT NULL,
  note                 TEXT
);

CREATE TABLE IF NOT EXISTS geos (
  geo_id           TEXT PRIMARY KEY,
  level            TEXT NOT NULL,
  name             TEXT NOT NULL,
  state            TEXT,
  parent_geo_id    TEXT,
  lat              REAL,
  lon              REAL,
  population       INTEGER
);

CREATE TABLE IF NOT EXISTS market_facts (
  geo_id           TEXT NOT NULL,
  period_start     TEXT,
  period_end       TEXT NOT NULL,
  cadence          TEXT NOT NULL,
  metric           TEXT NOT NULL,
  value            REAL,
  provider         TEXT NOT NULL,
  source_id        TEXT NOT NULL,
  PRIMARY KEY (geo_id, period_end, metric, provider)
);

CREATE TABLE IF NOT EXISTS macro_series (
  series_id        TEXT NOT NULL,
  ts               TEXT NOT NULL,
  value            REAL NOT NULL,
  provider         TEXT NOT NULL,
  source_id        TEXT NOT NULL,
  PRIMARY KEY (series_id, ts)
);

CREATE TABLE IF NOT EXISTS listings (
  listing_id       TEXT PRIMARY KEY,
  provider         TEXT NOT NULL,
  geo_id           TEXT,
  lat              REAL NOT NULL,
  lon              REAL NOT NULL,
  price            REAL,
  beds             REAL,
  baths            REAL,
  sqft             REAL,
  dom              INTEGER,
  status           TEXT,
  listed_at        TEXT,
  fetched_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sale_events (
  event_id          TEXT PRIMARY KEY,
  provider          TEXT NOT NULL,
  property_id       TEXT NOT NULL,
  address           TEXT,
  city              TEXT,
  state             TEXT,
  zip_code          TEXT,
  lat               REAL NOT NULL,
  lon               REAL NOT NULL,
  sale_date         TEXT NOT NULL,
  price             REAL,
  property_type     TEXT,
  beds              REAL,
  baths             REAL,
  sqft              REAL,
  fetched_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_usage (
  provider            TEXT NOT NULL,
  period              TEXT NOT NULL,
  attempted_requests  INTEGER NOT NULL DEFAULT 0,
  successful_requests INTEGER NOT NULL DEFAULT 0,
  reserved_requests   INTEGER NOT NULL DEFAULT 0,
  last_status         INTEGER,
  tracked_since       TEXT NOT NULL,
  updated_at          TEXT NOT NULL,
  PRIMARY KEY (provider, period)
);

CREATE TABLE IF NOT EXISTS provider_cache (
  provider          TEXT NOT NULL,
  cache_key         TEXT NOT NULL,
  payload_json      TEXT NOT NULL,
  fetched_at        TEXT NOT NULL,
  PRIMARY KEY (provider, cache_key)
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  run_id           TEXT PRIMARY KEY,
  started_at       TEXT NOT NULL,
  finished_at      TEXT,
  ok               INTEGER NOT NULL,
  summary_json     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS government_areas (
  area_id           TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  state             TEXT NOT NULL,
  county            TEXT NOT NULL,
  parent_geo_id     TEXT,
  provider          TEXT NOT NULL,
  source_id         TEXT NOT NULL,
  lat               REAL NOT NULL,
  lon               REAL NOT NULL,
  parcel_count      INTEGER,
  geometry_geojson  TEXT NOT NULL,
  observation_as_of TEXT,
  fetched_at        TEXT NOT NULL,
  note              TEXT
);

CREATE INDEX IF NOT EXISTS idx_facts_metric_period ON market_facts (metric, period_end);
CREATE INDEX IF NOT EXISTS idx_facts_geo ON market_facts (geo_id, period_end);
CREATE INDEX IF NOT EXISTS idx_listings_geo ON listings (geo_id);
CREATE INDEX IF NOT EXISTS idx_sale_events_date ON sale_events (sale_date);
CREATE INDEX IF NOT EXISTS idx_sale_events_location ON sale_events (lat, lon);
CREATE INDEX IF NOT EXISTS idx_government_areas_county ON government_areas (state, county);
"""


def connect(settings: Settings | None = None) -> sqlite3.Connection:
    settings = settings or get_settings()
    path: Path = settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    usage_cols = {r[1] for r in conn.execute("PRAGMA table_info(provider_usage)").fetchall()}
    if "reserved_requests" not in usage_cols:
        conn.execute(
            "ALTER TABLE provider_usage ADD COLUMN reserved_requests INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    for private_path in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        if private_path.exists():
            os.chmod(private_path, 0o600)
    return conn


def init_db(
    conn: sqlite3.Connection | None = None, settings: Settings | None = None
) -> sqlite3.Connection:
    owned = conn is None
    conn = conn or connect(settings)
    conn.executescript(SCHEMA)
    # Migrate older 'as_of' column name if present from a partial create.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sources)").fetchall()}
    if "as_of" in cols and "observation_as_of" not in cols:
        conn.execute("ALTER TABLE sources ADD COLUMN observation_as_of TEXT")
        conn.execute("UPDATE sources SET observation_as_of = as_of WHERE observation_as_of IS NULL")
    conn.commit()
    if owned:
        return conn
    return conn
