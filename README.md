# RealtyKit

RealtyKit is a local-first US housing research dashboard. It combines public
housing datasets, stock-market history, mortgage-rate context, government GIS
layers, freshness tracking, geographic search, trend charts, correlations, and
outlier detection in one map-oriented application.

The project has two processes:

- A Python/FastAPI backend that downloads, normalizes, caches, and serves data.
- A React/Vite frontend with Leaflet maps and Recharts visualizations.

RealtyKit does not scrape listing-site HTML. Compass remains unavailable until
a licensed API or MLS/RESO feed is configured. Zillow and Redfin integrations
use their public research datasets rather than consumer-page scraping.

## What the application provides

- Search by US city, ZIP code, or street address.
- Metro and ZIP-level housing maps where source data is available.
- Typical home value, inventory, new-listing, and days-on-market trends.
- Stock-market dips and housing/stock/mortgage correlation views.
- Market and listing outlier flags.
- Source-level observation dates, file dates, and stale-data warnings.
- Santa Clara County boundaries and parcel counts for Palo Alto, Santa Clara,
  Mountain View, Sunnyvale, and San Jose.
- Dated government-data snapshots with source URLs and SHA-256 provenance.

Government parcel layers provide geography and parcel context. They are not
automatically equivalent to verified deed sale prices.

## Technology

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Pydantic, httpx |
| Database | SQLite |
| Frontend | React, Vite |
| Mapping | Leaflet, React Leaflet, CARTO/OpenStreetMap tiles |
| Charts | Recharts |
| Tests | pytest |

## Prerequisites

- Python 3.11 or newer.
- Node.js 18 or newer. The locked Vite 5 release accepts Node 18 or 20+.
- npm.
- Internet access for live provider refreshes and map tiles.
- macOS, Linux, or a comparable Unix shell for the commands below.

Check installed versions:

```bash
python3 --version
node --version
npm --version
```

## Quick start

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

cp .env.example .env
cp web/.env.example web/.env

cd web
npm ci
cd ..
```

Add any desired keys to `.env` and `web/.env` as described in
[API keys and configuration](#api-keys-and-configuration).

Run an initial data refresh:

```bash
.venv/bin/realtykit ingest refresh
```

The app can still start without a live refresh. If the database is empty, the
backend loads the bundled fixture snapshot so developers can work on the UI.

Start the backend in terminal 1:

```bash
.venv/bin/realtykit serve --port 8770
```

Start the frontend in terminal 2:

```bash
cd web
npm run dev -- --host 127.0.0.1
```

Open:

- Dashboard: <http://127.0.0.1:5173>
- API health: <http://127.0.0.1:8770/api/health>
- Interactive API documentation: <http://127.0.0.1:8770/docs>

The Vite server proxies `/api` requests to `http://127.0.0.1:8770`.

## API keys and configuration

RealtyKit separates server-side credentials from browser configuration:

- Put backend values in `.env` at the repository root.
- Put Vite/browser values in `web/.env`.
- Both files are ignored by Git. Never commit real credentials.
- Restart the relevant process after changing an environment file.

### Key summary

| Variable | Required? | Used for | Where to obtain it |
|---|---:|---|---|
| `VITE_CARTO_BASEMAP_KEY` | Recommended | Raster basemap tiles without the API-key watermark | [CARTO Basemaps key request](https://carto.com/basemaps/apikey/) |
| `FRED_API_KEY` | Optional | Official FRED mortgage-rate API; public CSV and Freddie Mac fallbacks are attempted without it | [FRED API keys](https://fred.stlouisfed.org/docs/api/api_key.html) |
| `RENTCAST_API_KEY` | Optional | Active listing pins and home-level listing outliers | [RentCast API dashboard and setup](https://developers.rentcast.io/reference/introduction) |
| `CENSUS_API_KEY` | Not currently needed | Reserved for future Census Data API datasets | [Census Data API key request](https://api.census.gov/data/key_signup.html) |

RentCast currently advertises a small free development allowance; review its
current pricing before building a high-volume workflow. CARTO currently offers
a free basemap allowance but requires attribution and a key. Provider limits
and terms can change, so use the linked official pages as the authority.

### Backend `.env`

Copy `.env.example` to `.env` and fill only the values you need:

```dotenv
FRED_API_KEY=
RENTCAST_API_KEY=
CENSUS_API_KEY=

REALTYKIT_DATA_DIR=
REALTYKIT_RESOURCES_DIR=
REALTYKIT_HOST=127.0.0.1
REALTYKIT_PORT=8770
REALTYKIT_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
```

`REALTYKIT_DATA_DIR` changes where the SQLite database, raw market cache, and
probe files are stored. `REALTYKIT_RESOURCES_DIR` changes where dated
government snapshots are stored. Empty values use the repository's `data/`
and `resources/` directories.

The backend intentionally refuses non-loopback binds. It is designed as a
local research application, not as an internet-facing production service.

### Frontend `web/.env`

Copy `web/.env.example` to `web/.env`:

```dotenv
VITE_CARTO_BASEMAP_KEY=your_carto_basemap_key
```

Vite embeds all `VITE_` values in browser JavaScript. A CARTO basemap key must
therefore be treated as a client-visible project key, not as a private server
secret. Monitor its usage and apply provider-side restrictions when available.

After editing `web/.env`, restart `npm run dev`. If old unkeyed tiles remain,
force-refresh the browser because both browsers and tile CDNs cache images.

### Sources that do not need keys

The current adapters can access these sources without developer credentials:

- Zillow Research public datasets.
- Redfin Data Center public research files.
- Yahoo Finance chart data used for broad index history.
- Census Geocoder for address lookup.
- Census Gazetteer geography files.
- Freddie Mac PMMS public history as a FRED fallback.
- Santa Clara County public ArcGIS layers.
- San Mateo County public GIS metadata and downloads.

Public access does not guarantee a dataset is current. RealtyKit evaluates the
publisher's observation date independently from the download time.

### Compass and MLS data

Compass does not provide a public self-service listings API for this project.
The adapter reports `unavailable` and does not scrape Compass pages. To add
licensed listing coverage, use a broker-authorized MLS/RESO Web API, Bridge
Interactive, or another provider whose contract permits the intended use.

## Refreshing data

Refresh all configured providers:

```bash
.venv/bin/realtykit ingest refresh
```

Refresh selected providers:

```bash
.venv/bin/realtykit ingest refresh --providers zillow,yahoo,fred
.venv/bin/realtykit ingest refresh --providers government
.venv/bin/realtykit ingest refresh --providers rentcast
```

Supported provider names:

```text
zillow, redfin, yahoo, census, government, fred, compass, rentcast
```

Ignore HTTP cache validators and download again:

```bash
.venv/bin/realtykit ingest refresh --force
```

The dashboard's **Refresh** button calls the same local refresh workflow. The
refresh endpoint is loopback-only.

### What refresh changes

- Normalized data is written to `data/realtykit.db`.
- Provider downloads and HTTP metadata are cached under `data/raw/`.
- Government downloads are written under
  `resources/government/YYYY-MM-DD/`.
- Each government snapshot includes `manifest.json` with source URLs, fetch
  times, HTTP metadata, hashes, sizes, scope, and limitations.
- Existing last-good cache files can be used when a provider is temporarily
  unavailable.

For the government-only snapshot structure, see
[`resources/README.md`](resources/README.md).

## Data providers and behavior

| Provider | Main use | Key | Behavior when unavailable |
|---|---|---:|---|
| Zillow Research | Metro/ZIP inventory, DOM, new listings, ZHVI | No | Last-good or fixture data may remain visible and stale |
| Redfin Data Center | National housing history | No | Marked stale/unavailable; never represented as live |
| Yahoo | S&P 500, Nasdaq, Dow history and dip analysis | No | Source is marked unavailable |
| FRED / Freddie Mac | 30-year mortgage rates | Optional | FRED CSV, Freddie Mac PMMS, then last-good cache; never blocks housing ingest |
| Census | ZIP/metro geography and address geocoding | No for current features | Local geography remains; remote address search may be unavailable |
| Santa Clara County GIS | Five target-city boundaries and parcel counts | No | Existing dated snapshot remains available |
| San Mateo County GIS | Adjacent parcel/GIS reference | No | Source status records the failure |
| RentCast | Active listing pins and listing-level outliers | Yes | Feature remains empty and clearly labeled |
| Compass | Planned licensed listing integration | No supported public key | Always reports unavailable; no scraping |

## Freshness model

Every API response includes a freshness block. RealtyKit keeps separate clocks:

- `observation_as_of`: when the underlying market measurement applies.
- `http_last_modified`: when the publisher changed the downloadable file.
- `fetched_at`: when RealtyKit downloaded or checked the source.

A successful download today does not make an older observation current. This
is why a source can be file-fresh but observation-stale. The UI deliberately
shows stale warnings instead of relabeling old data as live.

Typical statuses are:

- `live`: current daily observation.
- `fresh`: within the application's freshness window.
- `aging`: outside the desired seven-day window but not deeply stale.
- `stale`: too old for a current-market claim.
- `by_design_monthly`: valid monthly series that should not be judged as daily.
- `unavailable`: no usable source observation.

## Using the dashboard

### Search and map

Use the search field for:

- A city, such as `Palo Alto` or `San Jose`.
- A five-digit ZIP code.
- A full US street address.

City searches center on official or stored city coordinates. Street addresses
use the Census Geocoder and then load metrics for the nearest tracked metro.
Market values shown after selecting a city boundary may be metro aggregates;
the UI labels that distinction.

The teal South Bay outlines are official Santa Clara County city boundaries.
Their parcel totals are address-derived coverage counts, not transaction counts
or sale prices.

### Dashboard tabs

- **Trends**: inventory, days on market, new listings, and value history.
- **Overlay**: normalized housing, stock, and mortgage-rate series.
- **Correlation**: aligned Pearson correlations with sample-size warnings.
- **Outliers**: unusual metro or listing observations and reasons.
- **Dips**: broad stock-index drawdowns and distance from recent lows.
- **Research**: selected-area metrics, source provenance, context, and caveats.
- **Sources**: source ledger, freshness, file dates, and provider limitations.

Correlation is descriptive, not evidence that stock prices or interest rates
caused a housing-market change.

## API reference

FastAPI generates live OpenAPI documentation at <http://127.0.0.1:8770/docs>.

| Method and path | Purpose |
|---|---|
| `GET /api/health` | Service health and overall freshness |
| `GET /api/freshness` | Full source ledger and freshness status |
| `GET /api/meta/freshness` | Alias for the freshness ledger |
| `GET /api/map/cities` | Metro map features for a selected metric |
| `GET /api/map/government-areas` | Official target-city geometries and parcel counts |
| `GET /api/map/zips?bbox=...` | ZIP inventory features inside a bounded viewport |
| `GET /api/map/listings?bbox=...` | Active listing pins when RentCast is configured |
| `GET /api/search?q=...` | Metro, city, ZIP, and address search |
| `GET /api/research?geo_id=...` | Area research, provenance, context, and limitations |
| `GET /api/kpis?geo_id=...` | Current KPI strip |
| `GET /api/trends?geo_id=...` | Historical metric series |
| `GET /api/correlation?geo_id=...` | Housing, stocks, and rates correlation |
| `GET /api/outliers?geo_id=...` | Metro and listing outliers |
| `GET /api/stocks/dips` | Broad-index dip analysis |
| `POST /api/ingest/refresh` | Start a local provider refresh |

Example requests:

```bash
curl http://127.0.0.1:8770/api/health
curl 'http://127.0.0.1:8770/api/search?q=Palo%20Alto'
curl 'http://127.0.0.1:8770/api/kpis?geo_id=zillow:metro:395059'
curl http://127.0.0.1:8770/api/map/government-areas
```

Refresh selected sources through the API:

```bash
curl -X POST http://127.0.0.1:8770/api/ingest/refresh \
  -H 'Content-Type: application/json' \
  -d '{"providers":["government","zillow"],"force":false}'
```

## Project layout

```text
realtykit/
├── realtykit/
│   ├── analysis/       # Correlation, alignment, dip, and outlier logic
│   ├── api/            # FastAPI app, schemas, dependencies, and routes
│   ├── ingest/         # Refresh orchestration and HTTP caching
│   ├── models/         # Pydantic/domain models
│   ├── providers/      # Provider-specific adapters
│   └── store/          # SQLite schema and repository functions
├── web/
│   ├── src/            # React application
│   ├── .env.example    # Frontend environment template
│   └── package.json
├── data/
│   ├── fixtures/       # Offline UI/API seed snapshot
│   ├── probe/          # Last-good research probe inputs
│   ├── raw/            # Download cache; ignored by Git
│   └── realtykit.db    # Local SQLite database; ignored by Git
├── resources/
│   └── government/     # Date-stamped official GIS snapshots
├── docs/
│   ├── metrics.md
│   └── research/
├── tests/
├── .env.example        # Backend environment template
└── pyproject.toml
```

## Development and verification

Install development dependencies with the editable backend install:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

Run backend tests:

```bash
.venv/bin/pytest -q
```

Run Python lint checks:

```bash
.venv/bin/ruff check realtykit tests
```

Build the frontend:

```bash
cd web
npm run build
```

Preview the production frontend build:

```bash
cd web
npm run preview -- --host 127.0.0.1
```

The frontend production bundle is written to `web/dist/`.

## Troubleshooting

### The page opens but API panels are empty

Confirm the backend is running on port 8770:

```bash
curl http://127.0.0.1:8770/api/health
lsof -i tcp:8770 -P -n
```

Then confirm the Vite server is on port 5173:

```bash
lsof -i tcp:5173 -P -n
```

### CARTO displays an API-key watermark

1. Put the key in `web/.env` as `VITE_CARTO_BASEMAP_KEY`.
2. Stop and restart the Vite process.
3. Force-refresh the page to discard cached unkeyed tiles.
4. Confirm CARTO/OpenStreetMap attribution remains visible.

### Listing pins are empty

This is expected without `RENTCAST_API_KEY`. Add the key to the root `.env`,
restart the backend, and refresh the `rentcast` provider. Viewport listing
requests are made only after the map is zoomed into a bounded area.

### Mortgage rates are unavailable

Add `FRED_API_KEY` to the root `.env` and restart the backend. The refresh also
attempts the public FRED CSV, official Freddie Mac PMMS file, and last-good
cache, but network failures can make every route unavailable temporarily.

### Data is marked stale immediately after refresh

Read the source's `observation_as_of` value. Refreshing updates `fetched_at`,
but it cannot advance the publisher's latest observation. This is expected
behavior, not a failed refresh.

### Start over with a clean database

Stop the backend first. Preserve the old file rather than deleting it:

```bash
mv data/realtykit.db data/realtykit.db.backup
```

Start the backend to recreate the schema and seed fixtures, then run a live
refresh when ready.

### Frontend environment changes are ignored

Vite reads `web/.env` when the dev server starts. Restart `npm run dev` after
changing any `VITE_` variable. A repository-root `.env` is not a replacement
for `web/.env`.

## Data and analytical limitations

- Zillow and Redfin research files are aggregates, not MLS listing feeds.
- Government parcel GIS layers do not necessarily expose sale consideration.
- Address-derived parcel counts can differ from legal parcel or transaction
  counts.
- Monthly metrics are not suitable for a seven-day freshness promise.
- Market correlation is not causation.
- Outlier scores are screening signals, not appraisal or investment advice.
- The app is a research tool, not financial, legal, lending, or appraisal
  advice.

Historical government-data research and the sale-event connector roadmap are
documented in [`docs/research/04-government-data.md`](docs/research/04-government-data.md).
Metric definitions are in [`docs/metrics.md`](docs/metrics.md).

## Attribution and provider terms

Keep required map attribution visible:

- © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)
- © [CARTO](https://carto.com/attributions)

Other data sources include Zillow Research, Redfin Data Center, the Federal
Reserve Bank of St. Louis/FRED, Freddie Mac, Yahoo Finance, the U.S. Census
Bureau, Santa Clara County, and San Mateo County. Review each provider's terms,
licenses, rate limits, and redistribution requirements before deployment.

This product uses the FRED API but is not endorsed or certified by the Federal
Reserve Bank of St. Louis.
