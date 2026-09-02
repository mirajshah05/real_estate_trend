# RealtyKit data extraction — live probe report

**Assessor date:** 2026-08-31  
**Freshness SLA:** observation as-of date ≤ 7 days (file `Last-Modified` reported separately)  
**Method:** live `HEAD`/`GET` + parse. No Compass/Zillow/Redfin listing HTML. No invented API keys. Giant files were HEADed or streamed, not fully downloaded.  
**Cache:** small artifacts under `realtykit/data/probe/`; national Redfin reused from `/tmp/realtykit-probe/national.tsv.gz`.

Two clocks matter:

| Clock | Meaning | Used for SLA? |
|-------|---------|---------------|
| File `Last-Modified` | When the host last wrote the object | Secondary (transport freshness) |
| Observation as-of | Latest `PERIOD_END` / week column / bar date inside the file | **Primary 7-day SLA** |

---

## 1. Redfin national market tracker (parsed)

**Object:** `https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/us_national_market_tracker.tsv000.gz`  
**HEAD:** HTTP 200, `Content-Length` 486,979, `Last-Modified` **Tue, 02 Jun 2026 18:15:46 GMT**  
**Local:** `/tmp/realtykit-probe/national.tsv.gz` (copied to `data/probe/us_national_market_tracker.tsv000.gz`)

### Parse results

| Field | Measured value |
|-------|----------------|
| Rows | 1,903 |
| Unique `PERIOD_DURATION` | **`30` only** (count 1,903) |
| Weekly (`PERIOD_DURATION=7`) rows | **0 — none exist in this file** |
| `PERIOD_END` range | 2012-01-31 → **2026-05-31** |
| Latest `LAST_UPDATED` | **2026-06-02 14:05:58.423 Z** |
| Regions | ` National` only |
| Property types | All Residential, Condo/Co-op, Multi-Family (2-4 Unit), Single Family Residential, Single Units Only, Townhouse |

Latest **All Residential** national row (observation 91 days old vs 2026-08-31):

| Field | Value |
|-------|-------|
| PERIOD_BEGIN / PERIOD_END | 2026-05-01 / **2026-05-31** |
| PERIOD_DURATION | 30 |
| MEDIAN_SALE_PRICE | 449,846 |
| NEW_LISTINGS | 648,351 |
| INVENTORY | 1,460,440 |
| MEDIAN_DOM | 42 |
| HOMES_SOLD | 464,811 |
| LAST_UPDATED | 2026-06-02 14:05:58.423 Z |

**SLA:** FAIL (observation 2026-05-31 = 91 days; file LM 2026-06-02 = 90 days).

### Sample row (first file row, Townhouse 2019-01)

```json
{
  "PERIOD_BEGIN": "2019-01-01",
  "PERIOD_END": "2019-01-31",
  "PERIOD_DURATION": "30",
  "REGION_TYPE": "national",
  "REGION": " National",
  "CITY": "National",
  "STATE_CODE": "US",
  "PROPERTY_TYPE": "Townhouse",
  "MEDIAN_SALE_PRICE": "245609",
  "NEW_LISTINGS": "50795",
  "INVENTORY": "117075",
  "MEDIAN_DOM": "53",
  "HOMES_SOLD": "31746",
  "LAST_UPDATED": "2026-06-02 14:05:58.423 Z"
}
```

This file is a useful **historical** US series, not a live weekly feed.

---

## 2. Redfin metro / city / zip — HEAD + metro stream

S3 prefix listing is denied (`AccessDenied`). Direct object URLs work for the canonical names (not the `us_*` aliases except national).

| Object | HTTP | Bytes | Last-Modified | Verdict |
|--------|------|------:|---------------|---------|
| `us_national_market_tracker.tsv000.gz` | 200 | 486,979 | 2026-06-02 | OK to ingest (stale) |
| `redfin_metro_market_tracker.tsv000.gz` | 200 | **111,494,355** | 2026-06-02 | Streamable; too slow/stale for MVP full ingest |
| `us_metro_market_tracker.tsv000.gz` | 403 | — | — | Wrong key |
| `city_market_tracker.tsv000.gz` | 200 | **1,001,106,945** | 2026-06-02 | **Too large for MVP** |
| `us_city_market_tracker.tsv000.gz` | 403 | — | — | Wrong key |
| `zip_code_market_tracker.tsv000.gz` | 200 | **1,548,403,907** | 2026-06-02 | **Too large for MVP** |
| `state_market_tracker.tsv000.gz` | 200 | 8,979,710 | 2026-06-02 | Optional later (~9 MB, still stale) |
| `county_market_tracker.tsv000.gz` | 200 | 241,131,599 | 2026-06-02 | Skip |
| `neighborhood_market_tracker.tsv000.gz` | 200 | 2,353,602,188 | 2026-06-02 | Skip |
| `redfin_covid19/weekly_housing_market_data_most_recent.tsv000.gz` | 200 | **829,986,565** | **2026-04-29** | Skip — 830 MB and *staler* than monthly |

### Metro stream (no full 111 MB download)

Read the first **6,000,000** compressed bytes, decompressed incrementally, scanned **263** TSV rows, stopped at first Austin/Seattle match.

- First match: `REGION=Seattle, WA metro area`, `PERIOD_DURATION=30`, `PERIOD_END=2016-03-31` (file is chronological; early rows are 2016)
- `LAST_UPDATED` on that row: **2026-06-02 14:33:24.470 Z** (same rebuild as national)
- Same column set as national (metro grain via `REGION_TYPE=metro`)

**Recommendation:** do **not** ingest Redfin city/zip/weekly-covid for MVP. Prefer **Zillow weekly metro** for freshness. If Redfin S3 ever updates (watch `Last-Modified`), add **metro-only** with period filter + column projection — never the 1.0 GB / 1.5 GB objects.

---

## 3. Zillow Research weekly inventory + DOM (+ new listings)

CDN: `https://files.zillowstatic.com/research/public_csvs/`. No key. Wide CSV (id columns + one column per week).

| File | Bytes | Last-Modified | Latest week col | Age vs 2026-08-31 | File SLA | Obs SLA |
|------|------:|---------------|-----------------|------------------:|----------|---------|
| `invt_fs/Metro_invt_fs_uc_sfrcondo_sm_week.csv` | 2,478,376 | **2026-08-25** 10:27:38 | **2026-08-15** | file 6d / obs **16d** | PASS | FAIL |
| `mean_doz_pending/Metro_mean_doz_pending_uc_sfrcondo_sm_week.csv` | 449,506 | **2026-08-25** 10:27:54 | **2026-08-15** | file 6d / obs **16d** | PASS | FAIL |
| `new_listings/Metro_new_listings_uc_sfrcondo_sm_week.csv` | 1,136,086 | **2026-08-25** 10:29:37 | **2026-08-15** | file 6d / obs **16d** | PASS | FAIL |

Zillow weekly files are rewritten on Tuesdays. The host object is ≤7 days old; the **latest week-ending observation is 16 days old**. This is the freshest *legal* housing series measured today. Treat it as “best available weekly,” not SLA-green. Surface the as-of date in the UI.

### Inventory (`invt_fs`, smoothed SFR+condo, week)

- Metros/rows: **928** (includes `United States` as `RegionType=country`)
- Weeks: 446 (2018-02-03 → 2026-08-15)
- Latest values: **US 1,124,795** · **Austin, TX 12,830** · **Seattle, WA 12,005**

### Mean days to pending (`mean_doz_pending`)

- Metros/rows: **350** (subset of inventory metros)
- Weeks: 447 (2018-01-27 → 2026-08-15)
- Latest values: **US 55.0** · **Austin, TX 87.0** · **Seattle, WA 43.0**

### New listings (bonus; 1.1 MB, 0.8 s)

- Metros/rows: **814**
- Latest values: **US 84,355** · **Austin, TX 620** · **Seattle, WA 1,008**

### Other Zillow objects (HEAD only unless noted)

| File | Bytes | Last-Modified | Notes |
|------|------:|---------------|-------|
| Metro ZHVI monthly (downloaded) | 4,459,358 | 2026-08-16 | 895 metros; latest col **2026-07-31** (31d). US 371,774 · Austin 424,339 · Seattle 740,579 |
| City ZHVI monthly | 93,567,045 | 2026-08-16 | Too large + monthly. Skip MVP |
| Zip ZHVI monthly | 123,065,811 | 2026-08-16 | Skip |
| Zip weekly inventory (smoothed) | 33,885,544 | 2026-08-25 | Feasible (~34 MB) for zip map; optional |
| Zip weekly inventory (raw) | 34,066,220 | 2026-08-25 | Same |

---

## 4. Macro: FRED + Yahoo (+ Stooq)

### FRED `MORTGAGE30US`

Measured **2026-08-31** — CSV path is **not usable right now**:

| Attempt | Result |
|---------|--------|
| Python `urlopen` `fredgraph.csv?id=MORTGAGE30US` | timeout 30s, 0 bytes |
| `curl` HTTP/2 same URL | `HTTP/2 stream 1 was not closed cleanly: INTERNAL_ERROR`, 0 bytes |
| `curl --http1.1` same URL | timeout 35s, 0 bytes |
| `fred.stlouisfed.org/data/MORTGAGE30US.txt` | HTTP/2 INTERNAL_ERROR; HTTP/1.1 hung then timed out |
| `api.stlouisfed.org/fred/series/observations?...&file_type=json` **without key** | not completed in this pass (official API requires a free key; none invented) |
| `HEAD https://fred.stlouisfed.org/series/MORTGAGE30US` | **200**, `Last-Modified: Thu, 27 Aug 2026 16:02:26 GMT` (4 days) |
| GET series HTML | timeout 15s |

**Last 5 CSV rows: not obtained.** Do not invent them. The series *page* was touched 2026-08-27 (Freddie Mac PMMS typically publishes Thursdays; 2026-08-27 was a Thursday), so the series is likely live behind Akamai/bot defenses.

**Adapter contract:** try `fredgraph.csv` with a short timeout; if it fails, use the official FRED API **only** with an operator-supplied `FRED_API_KEY` from env (free signup). Cache last-good CSV. Do not block housing ingest on FRED.

Architecture note: `01-architecture.md` said the no-key CSV “works.” Re-verified today: **it does not**, from this network.

### Yahoo Finance chart API (works)

`https://query1.finance.yahoo.com/v8/finance/chart/{symbol}` — no key.

| Symbol | Interval | Last close | Last date | Age | Points |
|--------|----------|-----------:|-----------|----:|-------:|
| `^GSPC` | 1wk / 2y | **7,686.14** | **2026-08-31** | **0** | 105 |
| `^IXIC` | 1wk / 2y | **26,370.89** | **2026-08-31** | **0** | 105 |

Daily last 5 closes (`interval=1d&range=5d`):

| Date | ^GSPC | ^IXIC |
|------|------:|------:|
| 2026-08-25 | 7,677.28 | 26,151.30 |
| 2026-08-26 | 7,675.70 | 26,130.20 |
| 2026-08-27 | 7,730.99 | 26,541.35 |
| 2026-08-28 | 7,711.76 | 26,402.42 |
| 2026-08-31 | 7,686.14 | 26,370.89 |

**SLA:** PASS. Use Yahoo for stocks and dip detection. Isolate behind a provider + User-Agent + backoff.

### Stooq

`https://stooq.com/q/d/l/?s=^spx&i=w` returned a **JS proof-of-work challenge** HTML (`This site requires JavaScript to verify your browser`). Unusable. Confirmed.

---

## 5. Legal listing APIs (docs + unauthenticated live probes)

No free unauthenticated listing endpoint returned data. All keyed APIs 401/403/405 without credentials.

### RentCast — **recommended listing adapter (when a key exists)**

| | |
|--|--|
| Docs | https://developers.rentcast.io/reference/property-listings · `/listings/sale` |
| Auth | `X-Api-Key` header. Live GET without key: **401 Unauthorized** |
| Geo | Query `latitude`, `longitude`, `radius` (miles, max 100), or city/state/zip/address |
| Payload | `latitude`/`longitude` on every listing; `listedDate`, `lastSeenDate`, `daysOnMarket`, `status`, `price` |
| Freshness (vendor claim) | Each listing updated **at least once/day**; new listings typically in API **12–24 hours** after publish |
| ≤7-day listings? | **Yes, if subscribed.** Sorted by `lastSeenDate` desc. Not usable in no-key MVP |

Also has `/markets` zip stats (separate from listings) — useful later for zip cards without a 34 MB CSV.

### RapidAPI Realty-in-US (Api Dojo)

| | |
|--|--|
| Host | `realty-in-us.p.rapidapi.com` · `POST /properties/v3/list` |
| Auth | `X-RapidAPI-Key` + `X-RapidAPI-Host`. Live HEAD: **401** |
| Geo | `postal_code` / city / `search_location` radius; bbox `lat_min`/`lat_max`/`lng_*`; responses include `coordinate.lat`/`lon` and `list_date` |
| Freshness | Can sort `list_date` desc; `listed_date_min` filter exists |
| Legal posture | **Unofficial reproduction of Realtor.com public pages.** Treat as a scraper wrapper. **Do not use in MVP.** Same class as unofficial Compass/Zillow RapidAPI hosts |

### ATTOM

| | |
|--|--|
| Property API | `https://api.gateway.attomdata.com/propertyapi/v1.0.0/...` · header `apikey` + `Accept: application/json` |
| Live | HEAD `/property/basicprofile` → **405** (method; GET would still need a key) |
| Geo | `latitude` + `longitude` + `radius` on `/property/*` and `/sale/snapshot` |
| Listings vs sales | Classic Property API is **assessor / recorded-sale** heavy. **Active MLS listings** are **Slipstream** `/ws/listings` and require **being licensed for each MLS** |
| ≤7-day live listings? | Only via Slipstream + MLS license, not the free/self-serve property snapshot |

### Bridge Interactive (RESO)

| | |
|--|--|
| Docs | https://bridgedataoutput.com/docs/platform/Dashboard/using-apis |
| Auth | MLS/partner **invite** → Dashboard server token. `Authorization: Bearer` or `access_token=` |
| Surface | RESO Web API (OData) recommended; Bridge Web API `GET /api/v2/{dataset_id}/listings` with `near` geo |
| Live | HEAD `/api/v2/test/listings` → **403 Forbidden** |
| ≤7-day listings? | **Yes, for licensed datasets** (this is real MLS). Not self-serve. Correct long-term Compass-adjacent path |

### Compass — **no public bulk listings API**

Live checks 2026-08-31:

- `https://www.compass.com/robots.txt` — **200**. `Disallow: /api/` plus agent/workspace paths. Sitemaps exist for for-sale/for-rent HTML.
- `https://developers.compass.com/` — **301** to an **internal** Compass team-directory page (`/internal/tech-infra/...`).
- `https://www.compass.com/developers` — **404**.
- `https://api.compass.com/` — **405**.
- Third-party indexes (APIs.io / API Evangelist, generated 2026-07): “Compass does not currently publish a public developer API portal.”
- Independent MCP/scraper projects state the site is SSR React with **no public JSON API** and that Compass ToS forbid automated crawling.
- HousingWire 2026: Compass shares nationwide inventory with **MLS partners** (MRED, The MLS/CLAW, Bright MLS) — that is MLS-to-MLS, not a public developer API.

**Do not scrape Compass.** Unofficial RapidAPI “Compass data” hosts are scrapers.

**MVP recommendation:** `CompassAdapter` returns `{status: "unavailable"}`.  
**Ingest path that is legal:** an **MLS CSV / RESO extract adapter** (operator drops a licensed CSV or wires Bridge/RESO credentials). That is how Compass listings would ever appear — via MLS, not Compass.com.

---

## 6. Census 2024 ZCTA gazetteer (map centroids)

`https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip`

- HEAD/GET: **200**, 1,013,803 bytes, `Last-Modified` **2024-08-30** (static vintage — expected)
- Zip contains `2024_Gaz_zcta_national.txt`
- Columns: `GEOID ALAND AWATER ALAND_SQMI AWATER_SQMI INTPTLAT INTPTLONG`
- Rows: **33,791** ZCTAs (+ header)
- Samples: 78701 → 30.270569, −97.742589 · 98101 → 47.610902, −122.336422 · 10001 → 40.750649, −73.997298

SLA N/A (reference geography). Download in 0.7 s. **Yes for MVP.**

---

## 7. Source scorecard

SLA = observation as-of ≤ 7 days vs **2026-08-31**. File LM noted in “measured as-of.”

| Source | Grain | Metrics | Typical lag | Measured as-of | 7-day SLA | MVP? |
|--------|-------|---------|-------------|----------------|-----------|------|
| Zillow weekly inventory | national + metro (928) | for-sale inventory | ~10–16d (Tue publish) | week **2026-08-15**; file LM **2026-08-25** | **FAIL** obs / PASS file | **Yes** |
| Zillow weekly mean DoZ pending | national + metro (350) | days to pending (DOM proxy) | ~10–16d | week **2026-08-15**; LM **2026-08-25** | **FAIL** obs / PASS file | **Yes** |
| Zillow weekly new listings | national + metro (814) | new listings | ~10–16d | week **2026-08-15**; LM **2026-08-25** | **FAIL** obs / PASS file | **Yes** |
| Zillow metro ZHVI | national + metro (895) | typical home value | monthly (~30d) | **2026-07-31**; LM 2026-08-16 | **FAIL** | **Yes** (price level / MoM) |
| Zillow city ZHVI | city | typical home value | monthly | LM 2026-08-16; ~93 MB | FAIL | **No** (size) |
| Zillow zip weekly inventory | zip | inventory | ~10–16d | LM 2026-08-25; **34 MB** | FAIL obs / PASS file | **Optional** (zip map) |
| Redfin national TSV | national | sale $, inventory, DOM, new listings, homes sold, … | monthly; S3 stuck | **2026-05-31** / LM **2026-06-02** | **FAIL** | **Yes** (history only) |
| Redfin metro TSV | metro | same as national | monthly; S3 stuck | LM **2026-06-02**; 111 MB | **FAIL** | **No** (size + stale) |
| Redfin city / zip TSV | city / zip | same | monthly; S3 stuck | 1.0 GB / 1.5 GB; LM 2026-06-02 | **FAIL** | **No** |
| Redfin “covid19” weekly TSV | mixed | weekly housing | stale dump | LM **2026-04-29**; 830 MB | **FAIL** | **No** |
| Yahoo `^GSPC` / `^IXIC` | national (index) | weekly + daily close | same day | **2026-08-31** | **PASS** | **Yes** |
| FRED `MORTGAGE30US` | national | 30y mortgage rate | weekly Thu | CSV **unreachable**; series page LM **2026-08-27** | **FAIL to fetch** | **Yes adapter** (env key / retry) |
| Stooq | national | OHLC | — | JS challenge | n/a | **No** |
| Census 2024 ZCTA | zip centroid | lat/lng, land area | vintage 2024 | file 2024-08-30 | N/A | **Yes** |
| RentCast listings | listing + lat/lng | price, DOM, status, geo | 12–24h (vendor) | 401 without key | n/a (no key) | **No key in MVP**; adapter stub |
| ATTOM Property / Slipstream | property / MLS listing | sales + licensed listings | varies | 405/licensed | n/a | **No** (license) |
| Bridge / RESO | listing (MLS) | live MLS + geo | hours | 403 without token | n/a | **No** (partner) |
| RapidAPI Realty-in-US | listing | Realtor.com-shaped | hours | 401; scraper TOS | n/a | **No** (legal) |
| Compass public API | listing | — | — | **does not exist** | n/a | **Stub + MLS CSV adapter** |

---

## 8. MVP ingest set (< 60 seconds, measured)

Measured download times on 2026-08-31 (this host). Budget leaves ~50 s for parse + SQLite upsert + FRED retry.

| # | Artifact | Size | GET time | Powers |
|---|----------|-----:|---------:|--------|
| 1 | Zillow metro weekly inventory | 2.5 MB | 2.2 s | US trend, metro map, inventory KPI |
| 2 | Zillow metro weekly DOM | 0.45 MB | 0.6 s | DOM KPI, correlation, outliers |
| 3 | Zillow metro weekly new listings | 1.1 MB | 0.8 s | New-listings KPI |
| 4 | Zillow metro ZHVI monthly | 4.5 MB | ~2 s | Price level + MoM city/metro view |
| 5 | Redfin national TSV.gz | 0.49 MB | cached / <1 s | Long US history (banner: stale as-of May 2026) |
| 6 | Yahoo `^GSPC` + `^IXIC` (1wk/2y + 1d/5d) | ~25 KB | <1 s | Stocks, dips, correlation |
| 7 | Census 2024 ZCTA zip | 1.0 MB | 0.7 s | Zip/point map **centroids** |
| 8 | FRED `MORTGAGE30US` | ~20 KB when it works | **timeout today** | Rates + correlation — **non-blocking** |

**Total housing+geo+stocks ≈ 10 MB, ~8 s download.** Well under 60 s.

### How this covers product goals

| Goal | MVP data |
|------|----------|
| US trend | Zillow US row (inventory / DOM / new listings) + Redfin national history |
| City/metro view | Zillow metro rows (Austin, Seattle, 350–928 MSAs). ZHVI for price; weekly for flow |
| Zip-or-point map | Census ZCTA centroids. **Metro graduated circles** at MSA lat/lng (derive from largest city or a small static MSA centroid table). True zip choropleth = add optional **34 MB** zip weekly inventory (still <60 s) |
| Stocks | Yahoo daily/weekly `^GSPC`, `^IXIC` |
| Rates | FRED adapter; degrade to “rates unavailable” if CSV/API fail |
| Correlation | Align Zillow week-ending Friday-ish columns to Yahoo weekly bars + FRED Thursday rates |
| Outliers | **No listing API in no-key MVP.** Compute metro z-scores on inventory Δ, DOM, ZHVI MoM. Label “market outliers,” not “homes.” Home pins require RentCast key **or** MLS CSV |

**Do not download:** Redfin city/zip/neighborhood/weekly-830MB, Zillow city/zip ZHVI.

**Honesty banner:** “Housing weeks through **2026-08-15** (published 2026-08-25). Stocks through **2026-08-31**. Redfin national through **2026-05**. Mortgage rates: live fetch failed.”

---

## 9. Commands / snippet that succeeded

Parse one housing file (Zillow weekly inventory) and one stock file (Yahoo `^GSPC`):

```python
import csv, gzip, json
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

TODAY = date(2026, 8, 31)
UA = {"User-Agent": "RealtyKitResearch/0.1"}

# --- housing: Zillow metro weekly inventory (already downloaded) ---
inv = Path("realtykit/data/probe/Metro_invt_fs_uc_sfrcondo_sm_week.csv")
with inv.open(newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
week_cols = [c for c in rows[0] if c[:4].isdigit()]
latest = week_cols[-1]
by_name = {r["RegionName"]: r[latest] for r in rows}
print("inventory latest_week", latest, "age_days", (TODAY - date.fromisoformat(latest)).days)
print("US/Austin/Seattle", by_name["United States"], by_name["Austin, TX"], by_name["Seattle, WA"])

# --- or Redfin national gzip ---
with gzip.open("/tmp/realtykit-probe/national.tsv.gz", "rt", encoding="utf-8", newline="") as f:
    durations = {row["PERIOD_DURATION"] for row in csv.DictReader(f, delimiter="\t")}
print("redfin PERIOD_DURATION", durations)  # {'30'}

# --- stocks: Yahoo weekly ---
url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1wk&range=2y"
with urlopen(Request(url, headers=UA), timeout=20) as resp:
    chart = json.loads(resp.read())["chart"]["result"][0]
meta = chart["meta"]
print("GSPC last_close", meta["regularMarketPrice"], "symbol", meta["symbol"])
```

Measured output (this run):

```
inventory latest_week 2026-08-15 age_days 16
US/Austin/Seattle 1124795.0 12830.0 12005.0
redfin PERIOD_DURATION {'30'}
GSPC last_close 7686.14 symbol ^GSPC
```

Probe runner (reproducible): `realtykit/data/probe/run_probes.py` → `realtykit/data/probe/probe_results.json`.

---

## 10. Adapter implications (for implementers)

1. **Freshness ledger** must store both `http_last_modified` and `observation_as_of`. Zillow weekly will be file-fresh and observation-stale; that is normal.
2. **Redfin:** HEAD national + metro only. Ingest national. Skip objects > 20 MB unless `Last-Modified` moves after 2026-06-02.
3. **FRED:** do not assume no-key CSV works. Env `FRED_API_KEY` optional; timeout 8 s; last-good cache.
4. **Listings:** RentCast when `RENTCAST_API_KEY` is set. Otherwise metro-level outliers + empty pin layer.
5. **Compass:** unavailable stub + `MlsCsvAdapter` (RESO/Bridge or operator CSV with lat/lng, list date, price).
6. **Never:** scrape Compass/Zillow/Redfin listing pages; never RapidAPI unofficial realtor/zillow/redfin/compass hosts; never full 1 GB+ Redfin dumps.

---

## Appendix A — Unauthenticated listing probe table

| Target | Result |
|--------|--------|
| `GET api.rentcast.io/v1/listings/sale?...` | 401 Unauthorized |
| `HEAD api.gateway.attomdata.com/propertyapi/v1.0.0/property/basicprofile` | 405 Method Not Allowed |
| `HEAD api.bridgedataoutput.com/api/v2/test/listings` | 403 Forbidden |
| `HEAD realty-in-us.p.rapidapi.com/properties/v3/list` | 401 Unauthorized |
| `GET stooq.com/q/d/l/?s=^spx&i=w` | 200 HTML JS challenge |
| Compass robots / developers / api | 200 robots; 301 internal; 404 / 405 — no public catalog |

## Appendix B — Security / credentials

No API keys, tokens, or connection strings were created or stored. Probe scripts call only public URLs. Future keys (`FRED_API_KEY`, `RENTCAST_API_KEY`) must come from environment / secret manager, never source.
