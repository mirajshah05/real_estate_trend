# RealtyKit Architecture

**Product:** Real Estate Analyzer (visualization-first market dashboard)  
**Date:** 2026-08-31  
**Status:** Implemented MVP with backend cleanup completed 2026-09-01
**Sibling:** JobKit is an engineering-family reference (FastAPI + Vite + local SQLite). It is **not** a product template.

This document is the implementation contract for a local-first US housing dashboard. The product is a map and chart surface. Ingest is a background job. The CLI exists only to refresh data and start the server.

---

## 0. Product framing (what we will and will not claim)

User goals, restated as product surfaces:

| # | Goal | Primary UI | Honest data path |
|---|------|------------|------------------|
| 1 | US housing market trends | National KPI strip + trend charts | Official research dumps (Zillow weekly; Redfin when fresh) |
| 2 | Connect Compass / Redfin / Zillow / others, ≤7 days old | Persistent freshness banner + Sources panel | Official dumps + keyed listing APIs. **No HTML scrape.** |
| 3 | City-level pricing-change map | Full-bleed MapLibre choropleth / graduated circles | Latest period from city-grain dump, centroids from Census gazetteer |
| 4 | Stock dips / lows | Overlay chart + dip markers | Yahoo chart API `query1.finance.yahoo.com` for `^GSPC` (and optional `^DJI`, `^IXIC`) |
| 5 | Homes vs stocks vs loan rates | Correlation panel | Aligned weekly series: housing metric + `^GSPC` + FRED `MORTGAGE30US` |
| 6 | Time-to-close / DOM, new listings, inventory | KPI cards + city drill charts | Zillow weekly inventory / DOM / new listings; Redfin tracker columns when fresh |
| 7 | Outlier homes | Map pins + table | Requires a **keyed listing API**. MVP substitutes **city-level outliers**. |
| 8 | Map of homes + charts for 2–7 | Single dashboard, not a wizard | Map is the home screen; charts are docks |

Hard constraint: do not scrape Compass, Zillow, or Redfin listing HTML. Those sites' ToS forbid it, unofficial RapidAPI "Realtor.com / Zillow / Redfin" wrappers are scrapers in disguise, and they will be treated as out of bounds.

### 0.1 Provider reality (as of 2026-08-31)

| Brand | Official surface we will use | What we will not do |
|-------|------------------------------|---------------------|
| **Zillow** | Research CSVs at `files.zillowstatic.com/research/public_csvs/`. Weekly inventory (~2.4MB, Last-Modified **2026-08-25**, within 7 days) and weekly DOM (~450KB, same date) are the freshness winners. City ZHVI monthly (~93MB, **2026-08-16**) is a monthly index — it will never satisfy a 7-day *observation* rule. | No Zillow listing HTML, no retired public Zestimate API, no unofficial RapidAPI scrapers. |
| **Redfin** | Data Center S3 dumps (`redfin-public-data.s3.us-west-2.amazonaws.com`). National tracker 487KB; metro 111MB; city **1.0GB**; zip **1.5GB**; weekly most-recent TSV **830MB**. All probed files Last-Modified **2026-06-02** — **stale vs the 7-day rule**. Redfin's own site still claims weekly Thursday updates; the public S3 objects have not moved since June. | No Redfin listing HTML. Do not treat S3 files as live just because a page says "updates weekly." |
| **Compass** | **None.** No public research dump, no self-serve listing API, no developer portal. Internal agent platform only; a future B2B API is hiring-talk, not a shippable adapter. | No Compass HTML scrape, no session-proxy, no "unofficial Compass API." Ship a stub adapter that reports `unavailable`. |
| **FRED** | `MORTGAGE30US` (Freddie Mac 30-year, weekly Thursday). CSV download works without a key; official API key is optional and free. | Do not hardcode a FRED key. |
| **Yahoo Finance** | Chart API `https://query1.finance.yahoo.com/v8/finance/chart/^GSPC`. Works. Unofficial but stable enough for a local dashboard; isolate behind a provider adapter with User-Agent and backoff. | Do not use Stooq as primary (JS challenge). Do not scrape Yahoo HTML. |
| **Census** | 2024 ZCTA gazetteer (~1MB) for zip centroids. Cartographic boundary files for optional later choropleth. | Do not download full TIGER nation shapefiles into the serving path. |
| **Listings (homes on the map)** | Keyed, licensed APIs only. Recommended first adapter: **RentCast** (`api.rentcast.io`, `X-Api-Key`, listings + `/markets` zip stats). Later: ATTOM, Bridge Interactive / RESO (MLS-permissioned). | No RapidAPI unofficial Realtor/Zillow/Redfin hosts. Those are scrapers. |

**Implication:** "Connect Compass, Redfin, and Zillow" is a *branding* wish. Architecturally we connect **named provider adapters**. Zillow research is real. Redfin research is real but currently stale. Compass is a vacant socket. Individual home pins are a **fourth** provider class (keyed listings), not a scrape of those three brands.

---

## 1. System diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         PROVIDERS (adapters only)                        │
│                                                                          │
│  Research dumps (no key)          Macro (keyed or public)   Listings     │
│  ┌────────────┐ ┌────────────┐    ┌──────────┐ ┌─────────┐  ┌─────────┐ │
│  │ Zillow CSV │ │ Redfin TSV │    │ FRED     │ │ Yahoo   │  │ RentCast│ │
│  │ weekly +   │ │ S3 gz      │    │ MORTGAGE │ │ chart   │  │ ATTOM / │ │
│  │ monthly    │ │ (often     │    │ 30US     │ │ ^GSPC   │  │ RESO    │ │
│  │            │ │  stale)    │    │          │ │         │  │         │ │
│  └─────┬──────┘ └─────┬──────┘    └────┬─────┘ └────┬────┘  └────┬────┘ │
│        │              │                │            │            │      │
│  ┌─────┴──────────────┴────────────────┴────────────┴────────────┴────┐ │
│  │ CompassAdapter → always {status: unavailable} until official API   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │ HTTPS + HEAD/ETag + Last-Modified
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     INGEST (CLI / POST /api/ingest/refresh)              │
│  1. Probe freshness (HEAD / Last-Modified / as-of date in file)          │
│  2. Skip download if ETag/Last-Modified unchanged                        │
│  3. Stream-decompress; never load 1GB city / 1.5GB zip into RAM          │
│  4. Column-project + period-filter + optional metro allowlist            │
│  5. Upsert derived rows; record source ledger                            │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     CACHE / STORE  (local, gitignored)                   │
│                                                                          │
│  data/raw/          optional object cache of last-good dumps (ETag)      │
│  data/realtykit.db  SQLite serving store (the only thing the API reads)  │
│                                                                          │
│  sources | geos | market_facts | macro_series | listings |               │
│  outliers | correlations | ingest_runs                                   │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     ANALYSIS (pure functions, replayable)                │
│  align_weekly() → returns / z-scores                                     │
│  correlation(housing, equity, mortgage, lags)                            │
│  stock_dips(drawdown, local-min)                                         │
│  outliers_geo()     city/zip vs national cohort                          │
│  outliers_listing() price/sqft + DOM vs city cohort  (needs listings)    │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     API  FastAPI  127.0.0.1 only                         │
│  /health  /freshness  /map/*  /kpis  /trends  /correlation               │
│  /outliers  /stocks/dips  /listings  /ingest/refresh                     │
│  Every payload includes a FreshnessBlock. Unknown fields rejected.       │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │ Vite proxy /api → :8840
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     REACT DASHBOARD  (the product)                       │
│                                                                          │
│  ┌─ FreshnessBanner (always on) ──────────────────────────────────────┐  │
│  │ Zillow weekly FRESH · Redfin STALE (as of 2026-06-02) · Compass — │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│  ┌─ Map (70%) ─────────────────────────┐ ┌─ Dock (30%) ──────────────┐ │
│  │ City price-change circles/choropleth│ │ KPIs · Trends · Corr      │ │
│  │ Optional listing pins (zoom ≥ 10)   │ │ Outliers · Sources        │ │
│  │ Outlier halo                        │ │ Stock dips overlay        │ │
│  └─────────────────────────────────────┘ └───────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

Process model (local-first):

```
realtykit serve          → uvicorn realtykit.api.main:app --host 127.0.0.1 --port 8840
cd web && npm run dev    → Vite :5173, proxy /api → 127.0.0.1:8840
realtykit ingest refresh → one-shot provider pull; safe to cron
```

The browser never talks to Zillow, Redfin, Yahoo, FRED, or RentCast. Keys stay on the FastAPI process. No secrets in `localStorage`.

---

## 2. Recommended module layout

```
realtykit/
├── README.md
├── pyproject.toml                  # hatchling, python>=3.11, console script `realtykit`
├── .env.example                    # FRED_API_KEY=, RENTCAST_API_KEY=  (empty placeholders)
├── .gitignore                      # .env, data/, web/node_modules/, .venv/
├── docs/
│   └── research/
│       └── 01-architecture.md      # this file
├── realtykit/                      # Python package
│   ├── __init__.py
│   ├── cli.py                      # ingest, serve, status  — secondary
│   ├── settings.py                 # pydantic-settings; env only, no hardcoded secrets
│   ├── models/
│   │   ├── geo.py                  # GeoId, GeoLevel
│   │   ├── freshness.py            # FreshnessStatus, FreshnessBlock
│   │   ├── market.py               # MarketFact, KpiSnapshot
│   │   ├── listing.py
│   │   ├── macro.py                # MacroPoint, DipEvent
│   │   └── analysis.py             # CorrelationResult, OutlierRow
│   ├── providers/                  # one module per vendor; no HTML parsers
│   │   ├── base.py                 # ProviderProbe, FetchResult
│   │   ├── zillow_research.py
│   │   ├── redfin_research.py
│   │   ├── compass.py              # stub: unavailable
│   │   ├── fred.py
│   │   ├── yahoo_chart.py
│   │   ├── census_gazetteer.py
│   │   └── rentcast.py             # optional; skipped if no key
│   ├── ingest/
│   │   ├── planner.py              # which files, which filters, given disk + freshness
│   │   ├── http.py                 # httpx, HEAD, stream GET, size/timeout caps
│   │   ├── stream_tsv.py           # gzip + csv.reader; column project; period filter
│   │   ├── stream_csv.py
│   │   └── refresh.py              # orchestrates probe → fetch → load → analyze
│   ├── store/
│   │   ├── db.py                   # sqlite3 schema + migrations
│   │   ├── facts.py
│   │   ├── listings.py
│   │   └── sources.py
│   ├── analysis/
│   │   ├── align.py
│   │   ├── correlation.py
│   │   ├── dips.py
│   │   └── outliers.py
│   └── api/
│       ├── main.py
│       ├── schemas.py              # request/response pydantic; explicit fields, no __all__
│       └── routes/
│           ├── freshness.py
│           ├── map.py
│           ├── kpis.py
│           ├── trends.py
│           ├── correlation.py
│           ├── outliers.py
│           ├── stocks.py
│           └── ingest.py
├── web/                            # React 18 + Vite 5 (same family as JobKit, different UX)
│   ├── package.json
│   ├── vite.config.js              # proxy /api → 127.0.0.1:8840
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                 # shell + router only
│       ├── api/client.js
│       ├── pages/
│       │   ├── Dashboard.jsx       # map-first home
│       │   ├── City.jsx            # drill route /city/:geoId
│       │   └── Sources.jsx
│       ├── map/
│       │   ├── MapView.jsx         # MapLibre GL
│       │   ├── CityLayer.jsx
│       │   ├── ListingLayer.jsx
│       │   └── OutlierLayer.jsx
│       ├── charts/
│       │   ├── TrendChart.jsx
│       │   ├── CorrelationChart.jsx
│       │   └── StockDipChart.jsx
│       └── components/
│           ├── FreshnessBanner.jsx
│           ├── KpiStrip.jsx
│           ├── Dock.jsx
│           └── OutlierTable.jsx
├── data/                           # gitignored
│   ├── raw/
│   ├── geo/                        # gazetteer, simplified GeoJSON
│   └── realtykit.db
└── tests/
    ├── test_freshness.py
    ├── test_stream_filter.py
    ├── test_correlation.py
    ├── test_outliers.py
    └── test_api_contract.py
```

### 2.1 Engineering family vs JobKit (copy the *how*, not the *what*)

Reuse from JobKit's *engineering* family:

- `pyproject.toml` + hatchling + `realtykit` console script
- FastAPI on loopback, Vite proxy `/api`
- pydantic v2 models, pydantic-settings for env
- SQLite as the local system of record
- pytest + ruff, Python 3.11+
- Secrets only from environment (never committed)

Do **not** copy JobKit's product modules. See §9.

### 2.2 Serving store schema (SQLite)

```sql
-- Every serving query hits these tables. Raw dumps are not queried at request time.

CREATE TABLE sources (
  source_id        TEXT PRIMARY KEY,          -- e.g. zillow:inv_week_city
  provider         TEXT NOT NULL,             -- zillow | redfin | fred | yahoo | census | rentcast | compass
  dataset          TEXT NOT NULL,
  url              TEXT NOT NULL,
  http_last_modified TEXT,                    -- raw Last-Modified header
  etag             TEXT,
  content_sha256   TEXT,
  bytes            INTEGER,
  fetched_at       TEXT NOT NULL,             -- UTC ISO
  as_of            TEXT,                      -- latest observation date inside the file
  cadence          TEXT NOT NULL,             -- daily | weekly | monthly | unknown
  freshness        TEXT NOT NULL,             -- live | fresh | aging | stale | unavailable | by_design_monthly
  note             TEXT
);

CREATE TABLE geos (
  geo_id           TEXT PRIMARY KEY,          -- zillow:city:12447 or census:zcta:94110
  level            TEXT NOT NULL,             -- nation | state | metro | city | zip
  name             TEXT NOT NULL,
  state            TEXT,
  parent_geo_id    TEXT,
  lat              REAL,
  lon              REAL,
  population       INTEGER
);

CREATE TABLE market_facts (
  geo_id           TEXT NOT NULL,
  period_start     TEXT NOT NULL,
  period_end       TEXT NOT NULL,
  cadence          TEXT NOT NULL,
  metric           TEXT NOT NULL,             -- see §3.1 metric catalog
  value            REAL,
  provider         TEXT NOT NULL,
  source_id        TEXT NOT NULL,
  PRIMARY KEY (geo_id, period_end, metric, provider)
);

CREATE TABLE macro_series (
  series_id        TEXT NOT NULL,             -- GSPC | MORTGAGE30US
  ts               TEXT NOT NULL,
  value            REAL NOT NULL,
  provider         TEXT NOT NULL,
  source_id        TEXT NOT NULL,
  PRIMARY KEY (series_id, ts)
);

CREATE TABLE listings (
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

CREATE TABLE outliers (
  outlier_id       TEXT PRIMARY KEY,
  kind             TEXT NOT NULL,             -- geo | listing
  subject_id       TEXT NOT NULL,             -- geo_id or listing_id
  method           TEXT NOT NULL,
  score            REAL NOT NULL,
  reasons_json     TEXT NOT NULL,
  run_id           TEXT NOT NULL,
  created_at       TEXT NOT NULL
);

CREATE TABLE correlations (
  run_id           TEXT NOT NULL,
  series_a         TEXT NOT NULL,
  series_b         TEXT NOT NULL,
  lag_weeks        INTEGER NOT NULL,
  pearson          REAL,
  spearman         REAL,
  n                INTEGER,
  window_weeks     INTEGER,
  created_at       TEXT NOT NULL,
  PRIMARY KEY (run_id, series_a, series_b, lag_weeks)
);

CREATE TABLE ingest_runs (
  run_id           TEXT PRIMARY KEY,
  started_at       TEXT NOT NULL,
  finished_at      TEXT,
  ok               INTEGER NOT NULL,
  summary_json     TEXT NOT NULL
);

CREATE INDEX idx_facts_metric_period ON market_facts (metric, period_end);
CREATE INDEX idx_facts_geo ON market_facts (geo_id, period_end);
CREATE INDEX idx_listings_geo ON listings (geo_id);
CREATE INDEX idx_listings_bbox ON listings (lat, lon);
```

Indexes are the serving contract. The 1GB city TSV is never joined at request time.

---

## 3. API contract

Base: `http://127.0.0.1:8840`. All JSON. Dates are ISO-8601 UTC. Unknown query keys → `422`. Bbox / geo_id / metric are allow-listed (injection defense: no raw SQL concatenation; bind parameters only).

### 3.1 Shared types

```ts
type FreshnessStatus =
  | "live"              // observed within 24h (stocks)
  | "fresh"             // as_of within 7 days
  | "aging"             // as_of 8–14 days, or weekly file one cycle late
  | "stale"             // as_of or Last-Modified older than 14 days when weekly expected
  | "by_design_monthly" // monthly index; cannot meet 7-day observation rule
  | "unavailable";      // no official adapter (Compass today)

interface FreshnessBlock {
  computed_at: string;            // API clock
  overall: FreshnessStatus;       // worst *relevant* status for this payload
  sources: Array<{
    source_id: string;
    provider: string;
    dataset: string;
    as_of: string | null;
    fetched_at: string | null;
    http_last_modified: string | null;
    cadence: "daily" | "weekly" | "monthly" | "unknown";
    status: FreshnessStatus;
    note: string;                 // human, e.g. "S3 Last-Modified 2026-06-02; dashboard will not pretend this is current"
  }>;
}

type Metric =
  | "median_sale_price"
  | "median_list_price"
  | "zhvi"
  | "price_change_yoy"
  | "price_change_mom"
  | "price_change_wow"
  | "inventory"
  | "new_listings"
  | "days_on_market"
  | "median_dom"
  | "homes_sold"
  | "pending"
  | "price_drop_share";
```

`overall` is **not** "green if any source is fresh." It is the worst status among sources that actually fed the payload. A city price-change map built only from stale Redfin city TSV is `stale` even if Zillow weekly inventory is fresh.

### 3.2 Endpoints

#### `GET /api/health`

```json
{ "ok": true, "service": "realtykit", "version": "0.1.0" }
```

#### `GET /api/freshness`

Full source ledger for the banner and Sources page. No analysis.

```json
{
  "freshness": { "computed_at": "2026-08-31T23:00:00Z", "overall": "stale", "sources": [] },
  "goal": { "max_age_days": 7, "honest_summary": "Zillow weekly inventory/DOM meet the 7-day goal. Redfin S3 dumps do not. Compass has no official feed. ZHVI is monthly by design." }
}
```

#### `GET /api/map/cities`

City-level layer for the national map. Default metric `price_change_yoy`.

| Query | Rules |
|-------|--------|
| `metric` | allow-list in §3.1 |
| `period` | `latest` (default) or `YYYY-MM-DD` period_end |
| `provider` | `auto` (prefer fresh Zillow weekly analog, else Redfin, else ZHVI) or explicit |
| `limit` | 1–4000, default 800 (top cities by population or by \|change\|) |

Response:

```json
{
  "freshness": { "computed_at": "...", "overall": "fresh", "sources": [] },
  "metric": "price_change_yoy",
  "period_end": "2026-08-23",
  "provider": "zillow",
  "features": [
    {
      "geo_id": "zillow:city:12447",
      "name": "San Francisco",
      "state": "CA",
      "lat": 37.77,
      "lon": -122.42,
      "value": -0.042,
      "inventory": 1840,
      "days_on_market": 31
    }
  ]
}
```

Frontend renders this as MapLibre circle layer (MVP) or joins a simplified city GeoJSON (later). Payload stays under ~800 rows × ~120 bytes ≈ 100KB.

#### `GET /api/map/zips`

Same shape as cities, but **requires** `metro=` or `bbox=`. Refuses nationwide zip dumps. This is how we never serve 1.5GB.

| Query | Rules |
|-------|--------|
| `metro` | metro geo_id **or** |
| `bbox` | `west,south,east,north` floats, max span 3° |
| `metric`, `period` | as above |

`400` if neither `metro` nor `bbox` is present.

#### `GET /api/map/listings`

Home pins. Empty array + `freshness.sources[rentcast]=unavailable` if no API key.

| Query | Rules |
|-------|--------|
| `bbox` | required, max span 1° at zoom hint ≥ 10 |
| `limit` | 1–500, default 200 |
| `status` | `active` (default) |

```json
{
  "freshness": { "computed_at": "...", "overall": "fresh", "sources": [] },
  "listings": [
    {
      "listing_id": "rentcast:123",
      "lat": 37.78,
      "lon": -122.41,
      "price": 1680000,
      "beds": 2,
      "baths": 2,
      "sqft": 1100,
      "dom": 47,
      "status": "active",
      "outlier_score": 2.8,
      "outlier_reasons": ["price_per_sqft_vs_city", "dom_vs_city"]
    }
  ]
}
```

#### `GET /api/kpis`

| Query | Rules |
|-------|--------|
| `geo` | `US` (default) or geo_id |

```json
{
  "freshness": { "computed_at": "...", "overall": "fresh", "sources": [] },
  "geo_id": "nation:US",
  "as_of": "2026-08-23",
  "kpis": {
    "median_list_price": { "value": 425000, "delta_wow": 0.004, "delta_yoy": 0.031, "status": "fresh" },
    "inventory":         { "value": 1420000, "delta_wow": 0.012, "delta_yoy": 0.18,  "status": "fresh" },
    "new_listings":      { "value": 72000,   "delta_wow": -0.02, "delta_yoy": 0.05,  "status": "fresh" },
    "days_on_market":    { "value": 36,      "delta_wow": 1,     "delta_yoy": -4,    "status": "fresh" },
    "mortgage_30y":      { "value": 6.58,    "delta_wow": 0.04,  "delta_yoy": -0.22, "status": "fresh" },
    "spx":               { "value": 5621.4,  "delta_1d": -0.008, "drawdown_52w": -0.041, "status": "live" }
  }
}
```

Each KPI carries its own status so the UI can grey a stale Redfin "homes sold" card while keeping live SPX.

#### `GET /api/trends`

| Query | Rules |
|-------|--------|
| `geo` | required |
| `metrics` | comma allow-list, max 6 |
| `from`, `to` | ISO dates; default last 5 years |
| `cadence` | `weekly` (default) or `monthly` |

```json
{
  "freshness": { "computed_at": "...", "overall": "fresh", "sources": [] },
  "geo_id": "zillow:city:12447",
  "cadence": "weekly",
  "series": {
    "inventory":       [{ "t": "2026-08-23", "v": 1840 }],
    "days_on_market":  [{ "t": "2026-08-23", "v": 31 }],
    "median_list_price": [{ "t": "2026-08-23", "v": 1495000 }]
  }
}
```

#### `GET /api/correlation`

| Query | Rules |
|-------|--------|
| `geo` | default `US` |
| `housing` | metric, default `median_list_price` (weekly) or `zhvi` if only monthly exists |
| `window_weeks` | 26–260, default 104 |
| `max_lag` | 0–26, default 12 |

```json
{
  "freshness": { "computed_at": "...", "overall": "fresh", "sources": [] },
  "aligned_cadence": "weekly",
  "n": 104,
  "pairs": [
    { "a": "housing_return", "b": "gspc_return",     "lag_weeks": 0, "pearson": 0.21, "spearman": 0.18 },
    { "a": "housing_return", "b": "mortgage_change", "lag_weeks": 0, "pearson": -0.34, "spearman": -0.31 },
    { "a": "gspc_return",    "b": "mortgage_change", "lag_weeks": 0, "pearson": -0.12, "spearman": -0.09 }
  ],
  "best_lags": [
    { "a": "mortgage_change", "b": "housing_return", "lag_weeks": 8, "pearson": -0.41, "note": "mortgage leads housing by 8 weeks in this window" }
  ],
  "disclaimer": "Correlation is not causation. Series are differenced weekly returns; levels are not compared raw."
}
```

#### `GET /api/outliers`

| Query | Rules |
|-------|--------|
| `kind` | `geo` (default, MVP) or `listing` |
| `geo` | nation or metro; required for `listing` |
| `metric` | for `geo`, default `price_change_yoy` |
| `limit` | 1–100, default 25 |

```json
{
  "freshness": { "computed_at": "...", "overall": "fresh", "sources": [] },
  "kind": "geo",
  "method": "modified_z_mad",
  "rows": [
    {
      "subject_id": "zillow:city:...",
      "name": "Austin, TX",
      "score": 3.6,
      "value": -0.11,
      "cohort_median": -0.02,
      "reasons": ["price_change_yoy vs all cities, |Mz| > 3.5"]
    }
  ]
}
```

#### `GET /api/stocks/dips`

| Query | Rules |
|-------|--------|
| `symbol` | allow-list `^GSPC` (default), `^DJI`, `^IXIC` |
| `lookback_days` | 30–4000, default 365 |
| `drawdown_pct` | default 0.05 |

```json
{
  "freshness": { "computed_at": "...", "overall": "live", "sources": [] },
  "symbol": "^GSPC",
  "last": { "t": "2026-08-29", "close": 5621.4, "drawdown_52w": -0.041 },
  "dips": [
    { "t": "2026-04-07", "close": 5020.1, "kind": "drawdown", "from_peak": -0.086, "peak_t": "2026-02-19" }
  ]
}
```

#### `POST /api/ingest/refresh`

Local-only mutation. No request body secrets. Optional JSON:

```json
{ "providers": ["zillow", "fred", "yahoo"], "force": false }
```

`force: false` respects ETag / Last-Modified. Returns the new `GET /api/freshness` payload plus `run_id`. CLI `realtykit ingest refresh` is the same function.

Do **not** expose this on a non-loopback bind. If bind address is ever not `127.0.0.1`, require a local token (JobKit-style) — but the product default is loopback-only, no login wall.

### 3.3 Error shape

```json
{ "error": { "code": "bbox_required", "message": "Zip map requires metro or bbox." } }
```

Stable `code` values: `bbox_required`, `unknown_metric`, `unknown_geo`, `provider_unavailable`, `stale_only`, `payload_too_large`.

`stale_only` is **not** an error for reads. Reads succeed with `freshness.overall=stale`. It is a warning code the UI can latch onto.

---

## 4. Frontend information architecture

The product is **one dashboard**, not a multi-step editor. JobKit's monolithic `App.jsx` workflow (token → factbase → render → coverage) is the anti-pattern.

### 4.1 Routes

| Route | Purpose |
|-------|---------|
| `/` | Map-first dashboard. Default national city price-change. |
| `/city/:geoId` | Same shell; map flies to city; dock opens city trends + local outliers. |
| `/sources` | Full freshness ledger, licenses, last ingest, "why Compass is empty." |

No onboarding wizard. First paint should show a map even with stale Redfin, as long as *some* `market_facts` exist. If the DB is empty, show a full-page "Run `realtykit ingest refresh`" empty state — that is the only CLI the UI mentions.

### 4.2 Layout (desktop, 1440+)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ FreshnessBanner   [Zillow weekly · fresh 6d] [Redfin · STALE 90d] [...] │
│                  [Last ingest 2h ago]                    [Refresh] [US] │
├──────────────────────────────────────────────┬──────────────────────────┤
│                                              │ KPI strip (compact)      │
│  MapLibre                                    │ price · inv · DOM · 30y  │
│   · city circles (national / zoom < 8)       │ SPX + drawdown           │
│   · zip choropleth (metro, zoom 8–11)        ├──────────────────────────┤
│   · listing pins (zoom ≥ 11, keyed API)      │ Dock tabs:               │
│   · outlier halo                             │  Trends | Correlation |  │
│                                              │  Dips | Outliers         │
│                                              ├──────────────────────────┤
│                                              │ Chart for active tab     │
├──────────────────────────────────────────────┴──────────────────────────┤
│ Attribution footer: Zillow Research · Redfin Data Center · FRED · …     │
└─────────────────────────────────────────────────────────────────────────┘
```

Mobile: map full-bleed; dock becomes a bottom sheet; freshness banner stacks.

### 4.3 Map vs charts (who owns which question)

| Question | Map | Chart |
|----------|-----|-------|
| Where did prices move? | Color / radius = `price_change_yoy` | Sparkline on hover; full series in Trends |
| Where is inventory building? | Toggle metric | Trends |
| Which homes are weird? | Pins + halo | Outlier table |
| Did stocks dip with housing? | none (national) | Dips + Correlation |
| Are rates leading prices? | none | Correlation lag heatmap |

The map is geographic. Correlation and stock dips are **not** painted as a US choropleth. They live in the dock so we do not invent fake county-level equity data.

### 4.4 Freshness banners (non-negotiable UX)

Three layers, always visible when relevant:

1. **Global banner** (top): one chip per provider. Color = status. Click → `/sources`.
2. **Panel caption**: every chart title includes `as_of` and status. Example: "Inventory · Zillow weekly · as of 2026-08-23 · fresh."
3. **Stale overlay** on the map when the *active metric's* provider is `stale`: diagonal hatch + "Showing Redfin city tracker last updated 2026-06-02 (90 days old). This is historical, not current."

Never hide a stale source to make the product look live. If the only city price layer is stale Redfin, the map still renders, hatched.

**Refresh** in the banner calls `POST /api/ingest/refresh` and polls `/api/freshness`. It is a convenience; the CLI is the durable path.

### 4.5 Recommended frontend stack (keep it thin)

- React 18 + Vite (JobKit family)
- `react-router-dom` (JobKit has none; we need routes)
- `maplibre-gl` + `react-map-gl` (or a thin MapLibre wrapper). OSM raster or a self-hosted Protomaps PMTiles. **No Mapbox token required.**
- Charts: `uPlot` or `recharts`. Prefer uPlot if series get long; recharts is fine for MVP.
- No Redux. Server state via `fetch` + React Query *or* a 40-line SWR hook. The DB is local; cache 15–30s.

Do not add a Chrome extension, a token splash screen, or a PDF preview.

---

## 5. Caching strategy (1GB city / 1.5GB zip)

The serving path is SQLite. Raw dumps are an ingest cache, not a query engine.

### 5.1 What to download

| File | Size (probed) | Last-Modified | MVP download? | How |
|------|---------------|---------------|---------------|-----|
| Zillow weekly inventory (metro/city/zip variants; pick metro + city) | 2.4MB class | 2026-08-25 | **Yes, always** | Full file; tiny |
| Zillow weekly DOM | 450KB | 2026-08-25 | **Yes, always** | Full file |
| Zillow weekly new listings / list price (same family) | small | same CDN | **Yes** | Full file |
| Zillow city ZHVI monthly | 93MB | 2026-08-16 | **Yes, once; then ETag** | Full file; monthly |
| Redfin national tracker | 487KB | 2026-06-02 | **Yes** | Full file; cheap, documents staleness |
| Redfin metro tracker | 111MB | 2026-06-02 | **Yes, stream-filter** | Do not keep unused columns |
| Redfin city tracker | **1.0GB** | 2026-06-02 | **Conditional** | Stream-filter; see §5.3 |
| Redfin zip tracker | **1.5GB** | 2026-06-02 | **No by default** | Opt-in per metro allowlist |
| Redfin weekly most-recent TSV | **830MB** | — | **No by default** | Prefer smaller tracker grains; if used, extract latest week only |
| Census ZCTA gazetteer | ~1MB | annual | **Yes** | Full file |
| FRED `MORTGAGE30US` CSV | <50KB | weekly | **Yes** | Full file |
| Yahoo `^GSPC` chart JSON | <100KB | daily | **Yes** | Full response, 5y daily |
| RentCast listings | per bbox | live | **On demand** | Never bulk-nationwide |

Planner rule: **prefer the smallest file that answers the question.** City price-change map → Zillow weekly city list price / inventory if the file exists and is fresh; else ZHVI monthly (label `by_design_monthly`); else Redfin city (label `stale` today).

### 5.2 Probe before GET

```
HEAD url
  If-None-Match: <stored etag>
  If-Modified-Since: <stored last-modified>
```

Skip the body when `304`. Still recompute freshness (`fetched_at` updates; `as_of` unchanged). Cap body size per dataset (city TSV 1.2GB max; refuse if `Content-Length` exceeds cap unless `force`).

### 5.3 Stream-filter (never `pandas.read_csv` a 1GB gz)

```
httpx.stream GET
  → gzip.GzipFile(streaming)
    → io.TextIOWrapper
      → csv.reader(delimiter='\t')
        → keep only allow-listed columns
        → keep rows where Period End >= cutoff OR Region is in metro/city allowlist
        → executemany upsert in chunks of 5_000
```

RAM budget: one chunk. Disk budget for `data/raw/`:

- Keep last-good **national + metro + zillow weeklies + ZHVI** (~200MB).
- **Do not retain** the raw 1.0GB / 1.5GB / 830MB files after a successful load unless `REALTYKIT_KEEP_RAW=1`.
- If kept, one generation only (overwrite).

### 5.4 What lands in SQLite

**Always (MVP, all geos that fit):**

- National + all metros, last **5 years** weekly (or monthly if that is all we have)
- All cities, **latest period only** for map metrics (`price_change_yoy`, inventory, DOM, new listings, median list)
- Top **200** cities by population: **5 years** of weekly history (for `/city/:id` trends)
- Macro series: full FRED + 5y daily SPX
- Gazetteer centroids for those cities + all ZCTAs (points only, ~1MB)

**On demand (later):**

- Zip facts for a watched metro: latest period for all zips in metro + 2y history for zips the user pins
- Listings for the current bbox, TTL 6 hours
- Redfin city **history** for a watched city (stream a second pass with a tighter Region filter)

**Never:**

- Full zip history nationwide
- Full city history nationwide from the 1GB file
- Serving queries that open the raw TSV

### 5.5 Derived size estimate (order of magnitude)

| Table | Rows (MVP) | Approx |
|-------|------------|--------|
| `geos` | ~30k cities + 33k ZCTA points | 10MB |
| `market_facts` latest-all-cities × 6 metrics | ~180k | 20MB |
| `market_facts` history top-200 × 260w × 6 | ~300k | 35MB |
| metro+nation history | ~100k | 15MB |
| `macro_series` | ~2k | <1MB |
| indexes | — | ~20MB |
| **Total serving DB** | | **~80–120MB** |

That is the point: a 1.5GB dump becomes a ~100MB product database if we refuse to import the long tail of history.

### 5.6 Request cache

- FastAPI: no Redis. Optional in-process TTL (30s) for `/map/cities` and `/kpis`.
- `Cache-Control: no-store` on `/freshness` and `/ingest/*`.
- `Cache-Control: private, max-age=30` on map/KPI/trend reads.

---

## 6. Meeting the 7-day freshness goal — honestly

The goal is a **product promise with a definition**, not a vibe.

### 6.1 Definition

A *layer* is **fresh** when the **latest observation date inside the dataset** (`as_of`) is ≤ 7 days before `now` (America/Los_Angeles for the user, stored as UTC). `Last-Modified` is a probe signal, not `as_of`. A file touched today that still ends at 2026-06-01 is stale.

Statuses used everywhere (API + banner):

| Status | Rule |
|--------|------|
| `live` | Daily series; last bar within 24h (Yahoo) |
| `fresh` | `as_of` ≤ 7 days |
| `aging` | 7 < `as_of` ≤ 14 days |
| `stale` | Weekly-or-faster series with `as_of` > 14 days, **or** `Last-Modified` > 14 days when we cannot parse `as_of` |
| `by_design_monthly` | Cadence is monthly (ZHVI, Case-Shiller). Shown, never called "live." |
| `unavailable` | No official feed |

### 6.2 Layer scorecard (2026-08-31)

| Layer | User goal | Status today | What the UI says |
|-------|-----------|--------------|------------------|
| Zillow weekly inventory / DOM / new listings | 2, 6, 8 | **fresh** (as_of ≈ 2026-08-25, 6 days) | "Current weekly market pulse (Zillow Research)" |
| Zillow city ZHVI | 1, 3 | `by_design_monthly` (2026-08-16) | "Monthly home-value index, not a 7-day print" |
| Redfin national / metro / city / zip S3 | 2, 3, 6 | **stale** (Last-Modified 2026-06-02, ~90 days) | Hatched map if this is the active layer; "historical dump" |
| FRED `MORTGAGE30US` | 5 | **fresh** if last Thursday is within 7 days (weekly by construction; one week of lag is normal) | "Freddie Mac 30-year via FRED" |
| Yahoo `^GSPC` | 4, 5 | **live** | "Market close / last quote" |
| Compass | 2 | **unavailable** | Chip: "No official API — not scraped" |
| RentCast listings | 7, 8 home pins | **fresh** only after a keyed pull for the current bbox | "Listing sample, {n} homes, fetched {t}" |
| Census gazetteer | map geometry | annual, ignore for 7-day | Not shown as a market source |

### 6.3 How we *try* to stay within 7 days

1. **Nightly (or on banner Refresh):** probe Zillow weeklies, FRED, Yahoo. These are the honest 7-day core.
2. **HEAD Redfin S3 every ingest.** The day Last-Modified moves, stream-filter and flip the chip from stale → fresh. Until then, do not re-download 1GB.
3. **Do not substitute scrape** when a dump is stale. Stale + labeled beats illegal + "fresh."
4. **Provider preference for `auto`:** among adapters that supply the requested metric, pick the freshest status, then the finest grain. Example: city inventory → Zillow weekly city (fresh) over Redfin city (stale).
5. **Compass stays empty.** The Sources page explains the socket. When Compass publishes an official keyed API or research dump, fill the adapter. Not before.
6. **Listings are a different clock.** A 7-day-old *market dump* can still sit next to *today's* bbox listings. The banner shows both chips. Do not average them into one green light.

### 6.4 What we will never do to "make it fresh"

- Scrape listing HTML from Compass / Zillow / Redfin / Realtor.com
- Use unofficial RapidAPI hosts that wrap those sites
- Backfill `as_of` with `fetched_at`
- Report Redfin as current because the marketing page says "updates every Thursday"
- Invent city-level stock prices
- Use Stooq as primary after the JS challenge (keep as a commented fallback only if it starts returning CSV again)

---

## 7. Algorithm sketches

All analysis is **pure** and **replayable**: inputs are tables + a `run_id`. No LLM in the scoring path.

### 7.1 Alignment (shared)

Weekly Friday index. For each series:

- Housing weekly: use the provider's period-end.
- Housing monthly (ZHVI): hold last value through the month; **do not** interpolate a fake weekly ZHVI for correlation *levels*. For correlation *returns*, use month-end to month-end and compare to monthly-averaged SPX / mortgage — or drop ZHVI from the weekly correlation and use weekly list price instead.
- Mortgage: Thursday print, mapped to that week's Friday.
- SPX: Friday close; if holiday, last available close that week.

Transformations for correlation (default):

```
r_housing_t  = log(P_t) - log(P_{t-1})     # or Δ inventory / inventory
r_gspc_t     = log(C_t) - log(C_{t-1})
d_mort_t     = rate_t - rate_{t-1}         # already in percent points
```

Raw levels of ZHVI vs SPX are a chart option, never the correlation number.

### 7.2 Correlation

For window `W` (default 104 weeks) and lag `ℓ ∈ [-L, L]`:

```
pearson  = corr( x[t], y[t-ℓ] )
spearman = corr( rank(x[t]), rank(y[t-ℓ]) )
```

Pairs:

- `r_housing` × `r_gspc`
- `r_housing` × `d_mort`
- `r_gspc` × `d_mort`

Report `n`, both coefficients, and the lag that maximizes `|pearson|` with a minimum `|n|` of 40. UI copy is mandatory: **"Correlation is not causation."**

Later (not MVP): rolling 52-week correlation as a time series in the dock; Newey–West p-values if we want academic costume. Skip Granger until someone asks — it will be misread as proof.

### 7.3 Stock dips / lows

Two detectors, both on daily `^GSPC`:

1. **Peak drawdown events:** a dip starts when close ≤ peak_52w × (1 − `drawdown_pct`) (default 5%). It ends when close makes a new 52-week high, or after 60 sessions. Record trough date, depth, peak date.
2. **Local lows:** close is the minimum of a 20-session window and is ≥ 2% below the window's first close (filters flat markets).

The dock lists events. The chart marks troughs. We do not call these "buy signals."

### 7.4 Outliers

**MVP — geo outliers** (no listing API required):

Cohort = all cities with population ≥ 50k and a value for metric `m` in the latest period.

```
med = median(values)
mad = median(|v - med|)
Mz  = 0.6745 * (v - med) / (mad + ε)
```

Flag `|Mz| ≥ 3.5`. Reasons are data, not prose: `price_change_yoy vs cities, Mz=3.6`. Same method for inventory WoW and DOM.

**Later — listing outliers** (RentCast / RESO):

For each listing in a city (or zip if n ≥ 30):

| Signal | Score |
|--------|--------|
| `price / sqft` vs city median | `Mz` |
| `dom` vs city median | `Mz` |
| `price` vs city ZHVI or median list (if no AVM) | residual / MAD |
| beds/baths/sqft sanity | hard rules: sqft < 200, price ≤ 0, lat/lon outside US box → discard, not "outlier" |

Combine: `score = max(|Mz_ppsf|, 0.7|Mz_dom|, 0.5|Mz_vs_index|)`. Flag `score ≥ 3.0`. Store `reasons_json` as a list of fired signals.

Do **not** use an LLM to "explain" an outlier. A sentence template is enough: "Listed 38% above city median $/ft² and 2.1× city median DOM."

### 7.5 Time-to-close

Research dumps usually give **days on market** / **median days to pending**, not a true contract-to-close legal clock. Label the KPI **Days on market**, not "time-to-close," unless a provider column is explicitly pending-to-close. If Redfin exposes both, map them to distinct metrics (`days_on_market`, `days_to_close`) and never conflate.

---

## 8. Risks and phased delivery

### 8.1 Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Redfin S3 stays stuck at 2026-06-02 | High for goals 2–3 if we depended on it | Zillow weekly is the freshness backbone; Redfin is overlay |
| Compass never offers an official API | Medium (user asked to "connect Compass") | Stub + Sources copy; do not scrape |
| 7-day goal is physically impossible for monthly ZHVI | Medium (expectation) | `by_design_monthly` status; educate in banner |
| Unofficial Yahoo chart API breaks | Medium | Adapter + recorded last-good series; optional later Stooq/FRED `SP500` |
| FRED `SP500` is a weekday series but delayed | Low | Prefer Yahoo for dips; FRED as backup |
| RentCast quota (50 free calls/month) | High for home pins | Viewport-only fetch, 6h TTL, city-outlier MVP without pins |
| RapidAPI scrapers look like "the easy path" | High (ToS / legal) | Architecture ban; code review reject |
| 1GB stream on a laptop fills disk | Medium | Caps, delete raw after load, zip opt-in |
| MapLibre + full zip polygons explode the browser | High | Centroids first; zip polygons only inside one metro, simplified |
| Attribution / Zillow ToU | Medium | Footer attribution; local-only use; no republish of dumps |
| Treating correlation as a trading product | Medium (product risk) | Disclaimer on the panel; no alerts that say "buy houses" |
| Loopback API later bound to 0.0.0.0 | High | Default 127.0.0.1; ingest POST denied off-loopback |

### 8.2 Phased delivery

**Phase 0 — repo skeleton (days, not weeks)**  
`pyproject.toml`, FastAPI hello, Vite shell, MapLibre blank US view, `/api/freshness` returning empty sources, this doc. No JobKit files copied.

**Phase 1 — MVP dashboard (the product starts existing)**  
Ingest: Zillow weeklies + ZHVI city + FRED + Yahoo + Census gazetteer.  
API: `/freshness`, `/map/cities`, `/kpis`, `/trends`, `/correlation`, `/stocks/dips`, `/outliers?kind=geo`.  
UI: banner, city-circle map, KPI strip, Trends + Correlation + Dips tabs.  
CLI: `ingest refresh`, `serve`.  
Success: a user sees a US price/inventory map and can tell, in one glance, which layers are fresh. Compass chip is grey. Redfin is absent or present-but-stale if we already loaded national 487KB.

**Phase 2 — Redfin as historical / opportunistic live**  
Stream-filter metro (always) and city (latest-only). Zip still off. If S3 Last-Modified moves, the same pipeline goes green without a rewrite. City outliers can blend Zillow + Redfin when both exist.

**Phase 3 — Homes on the map**  
RentCast (or ATTOM) adapter, env key, bbox listings, listing outliers, `/map/listings`. Empty-state CTA: "Add RENTCAST_API_KEY to enable home pins." Do not fake pins from research dumps.

**Phase 4 — Metro zip choropleth + watched markets**  
`GET /api/map/zips?metro=`. Simplified Census cartographic ZCTA clipped to metro. Optional Redfin zip stream for that metro only.

**Phase 5 — Compass / MLS if and only if official**  
Fill `providers/compass.py` or a RESO/Bridge adapter when credentials and a license exist. Still no HTML.

**Explicitly out of scope for v1**

- Multi-user SaaS, auth, cloud deploy
- Chrome extension, form fill, trust ladders
- Automated trading / alert SMS
- Nationwide listing crawl
- LLM market commentary as a source of truth

---

## 9. What NOT to copy from JobKit

JobKit is a **job-apply pipeline** with a local editor. RealtyKit is a **market dashboard**. Sharing a FastAPI+Vite family is not permission to clone the product shape.

### 9.1 Do not copy these product ideas

| JobKit thing | Why it must not land here |
|--------------|---------------------------|
| CLI-first UX (`jobkit render` as the point) | The dashboard is the product. CLI is ingest/serve only. |
| Chrome MV3 extension, form fill, submit authority | There is nothing to submit. |
| Trust ladder / consecutive-clean / armed auto-submit | No analog. |
| Factbase → Typst/DOCX → parse/layout gates | No resume, no PDF pipeline. |
| Greenhouse / Lever / Ashby handlers | Different industry. Do not invent "Compass handlers" that drive a browser. |
| Playwright apply loops, `scripts/agent_apply_*.py` | No browser automation against listing sites. |
| Feashliaa / job CDN sourcing | Different data problem. Housing dumps are files + APIs. |
| Ledger of applications and confirmation artifacts | Replace with a **source freshness ledger**, not a submission ledger. |
| Token splash + `data/.token` as the first UI | Loopback dashboard; no editor secret by default. |
| Single 900-line `App.jsx` workflow | Routes + map/dock components. |
| Profile / essays / sponsorship / denylist | Irrelevant PII surface. Do not store the user's job-apply profile here. |
| `docs/JOBKIT_AGENT_MEMORY.md` apply runbook | Different agent job. Write a short ingest runbook later if needed. |
| Fabrication/coverage guards for generated bullets | No generated resume text. Keep *data* honesty via freshness statuses instead. |

### 9.2 Do not copy these files or folders

Do not `cp -R` `jobkit/jobkit/{handlers,submit,tailor,render,guards,profile,sourcing,retrievability,extension,ledger}` into RealtyKit. Start empty.

### 9.3 Patterns that *are* fine to re-implement (not copy-paste blindly)

- `pydantic-settings` + `.env` for keys
- SQLite module with a `SCHEMA` string and small repository functions
- Vite `/api` proxy
- `cli.py` with `serve` / subcommands
- pytest layout under `tests/`
- Loopback bind default

If a function is copied, it should be *rewritten* against RealtyKit names. Shared "kit" DNA is the stack, not a monorepo package.

---

## 10. Security and compliance notes (implementation constraints)

These are design rules for whoever implements next. They are not optional polish.

- **No hardcoded credentials.** `FRED_API_KEY`, `RENTCAST_API_KEY`, any future MLS secret: environment only. `.env` gitignored. `.env.example` has empty names, no values. (Applied because this repo must stay treat-as-public.)
- **No unofficial scrapers.** Provider modules fetch documented dump URLs or vendor REST with a key. If a dependency's docs say "wraps Zillow search HTML," reject it.
- **SQL.** Parameterized only. `geo_id`, `metric`, `bbox` validated against allow-lists / numeric ranges before query construction. Dynamic table/column names are not used.
- **SSRF.** Provider URLs are constants in code, not user-supplied. Ingest does not accept a raw URL from the client.
- **Loopback.** API binds `127.0.0.1`. CORS allow-list `http://127.0.0.1:5173` and `http://localhost:5173`.
- **Listings PII.** Store the minimum listing fields in §2.2. Do not log API keys or full RentCast payloads. Structured logs: `source_id`, `run_id`, row counts, status — not addresses in INFO.
- **Attribution.** Zillow Research, Redfin Data Center, Freddie Mac via FRED, Yahoo Finance, Census Bureau — footer on every view that uses them.
- **Certificates.** If anyone later pins or embeds a PEM for a provider, it must be loaded from a file and checked for expiry / key strength / SHA-2. Do not bake `BEGIN CERTIFICATE` into Python.

---

## 11. Open decisions (do not block Phase 1)

1. **Map basemap:** OSM raster vs Protomaps PMTiles shipped in `data/geo/`. OSM is faster to ship; PMTiles is nicer offline.
2. **RentCast vs ATTOM vs wait-for-RESO** for Phase 3. RentCast is the cheapest experiment; RESO is the correct long-term listing source if the user has MLS access.
3. **Keep raw Redfin city file or not.** Default no. Disk is the constraint, not CPU.
4. **Port.** `8840` suggested so it does not collide with JobKit's `8765`. Change freely.
5. **Whether Phase 1 includes Redfin national 487KB.** Yes, recommended — cheap and makes the stale chip real instead of theoretical.

---

## 12. Definition of done for "architecture accepted"

Implementation may start when the implementer agrees to all of the following:

1. Visualization-first; CLI is ingest/serve only.
2. Provider adapters only; Compass is `unavailable`; no HTML scrape.
3. Every API payload carries a `FreshnessBlock`; stale data is shown as stale.
4. SQLite is the serving store; 1GB/1.5GB files are stream-filtered or skipped.
5. Home pins require a keyed listing API; MVP outliers are cities, not invented homes.
6. Correlation uses differenced weekly series and a visible disclaimer.
7. Nothing is copied from JobKit's apply/extension/ledger/factbase product.

This file is the spec. Do not implement in this research pass.
