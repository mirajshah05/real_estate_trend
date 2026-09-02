# RealtyKit orchestration

**Product:** visualization-first full-stack US housing dashboard  
**Repo:** repository root (empty git repo at orchestration time)  
**Not:** JobKit. Do not clone `jobkit/` or its apply/resume/extension stack.

**Research status (compile 2026-08-31):** `01`, `02`, and `03` are in. §7 ADR is compiled from all three. Spawn A/B/C.

---

## 1. Agent roster

### Persistent project agents (already created)

| Agent | File | Use when |
|-------|------|----------|
| `realtykit-data` | `.cursor/agents/realtykit-data.md` | Ingest, providers, cache, ≤7-day freshness |
| `realtykit-frontend` | `.cursor/agents/realtykit-frontend.md` | Map, charts, dashboard UI |
| `realtykit-analyst` | `.cursor/agents/realtykit-analyst.md` | Correlation, outliers, stock dips, DOM/inventory math |

Workspace root for those files: `<workspace>/.cursor/agents/`.

### Research specialists (parallel, write-once reports)

| Report | Owner topic | Path |
|--------|-------------|------|
| Architecture | stack, services, API shape | `docs/research/01-architecture.md` |
| Reuse | what (if anything) to borrow — **not** JobKit product code | `docs/research/02-reuse.md` |
| Data extraction | sources, freshness, legal/ToS posture | `docs/research/03-data-extraction.md` |

### Follow-on implementers (spawn after compile)

| Spawn | Role | Persistent agent to attach |
|-------|------|----------------------------|
| **A** | Backend: providers + analysis + FastAPI | `realtykit-data` + `realtykit-analyst` prompts; single implementer owns backend tree |
| **B** | React map dashboard | `realtykit-frontend` |
| **C** | pytest + probe scripts | no persistent agent yet — spawn as test writer |

Skill for any coding agent in this product: `.cursor/skills/realtykit-analyze/SKILL.md`.

---

## 2. Compile protocol (parent executes when reports land)

Do not wait forever. If a report is missing after a short check, keep this plan and compile incrementally.

1. **Ingest** — Read `01-architecture.md`, `02-reuse.md`, `03-data-extraction.md` in full.
2. **Diff** — List agreements, conflicts (stack, source choice, reuse), and gaps vs product goals (below).
3. **Decide** — Write **§7 Architecture decision record** in this file (replace the pending stub). Lock:
   - backend language/framework
   - frontend framework + map + chart library
   - provider list + fallbacks
   - API resource names
   - what is explicitly **not** reused from JobKit
4. **Propagate** — Update the stack table in `.cursor/skills/realtykit-analyze/SKILL.md` so it is no longer “provisional.”
5. **Spawn** — Launch A/B/C with the file-ownership table in §4. Do not give two agents the same writable glob.
6. **Integrate** — After A and B report API + UI ready, C’s probes must pass freshness and city-click contracts.

### Product goals the compile must not drop

1. US market trends  
2. Compass / Redfin / Zillow / others; listing/city data **≤ 7 days**  
3. City price-change map  
4. Stock dips / lows  
5. Correlation: homes vs stocks vs mortgage rates  
6. DOM / new listings / inventory  
7. Outlier homes  
8. Map + charts as primary UI  

---

## 3. Implementation phases

### Phase 0 — Orchestration (this pass)

- [x] Project agents + analyze skill  
- [x] This file  
- [x] Compile ADR from `01` + `02` (wait on `03` for vendor live-test lock)  

### Phase 1 — Contracts (Agent A first 30–60 min, before B/C go deep)

- Pydantic models: city/market summary, listings slice, freshness, correlation, dips, outliers, geo feature  
- Fixture JSON under `data/fixtures/` so B can render without live vendors  
- `docs/metrics.md` stub (analyst constants; stdlib `statistics` for MVP)  

### Phase 2 — Parallel build

- **A:** `realtykit/` package — ingest, analysis, FastAPI, `realtykit serve --port 8770`  
- **B:** `web/` Vite app — Leaflet map, Recharts, freshness chip, city drawer, outlier panel  
- **C:** pytest for analysis + freshness; probe scripts hitting local API  

### Phase 3 — Vertical slice

- One city (e.g. Austin or a fixture MSA) end-to-end: refresh → API → map click → charts  
- Freshness chip reflects real `as_of`  
- At least one equity dip series and one mortgage series on a chart  

### Phase 4 — MVP harden

- Multi-city choropleth (or marker fallback)  
- Stale-source warning (`freshness_hours > 168`)  
- README: env vars, run, refresh, legal/source notes  

---

## 4. File ownership (no collisions)

Locked tree from `02-reuse.md` (JobKit **pattern only** — not JobKit domain code). Do not invent `backend/` + `frontend/` in parallel.

```
realtykit/
  pyproject.toml              # Agent A
  realtykit/                  # Agent A — Python package
    api/main.py
    cli.py                    # `realtykit serve --port 8770`
    ingest/                   # providers + httpx file cache
    models/
    store/                    # sqlite + cache
    analysis/
  web/                        # Agent B — Vite + React
    src/
      App.jsx
      MapPanel.jsx
      TrendCharts.jsx
      api.js
    vite.config.js
  tests/                      # Agent C
  scripts/probes/             # Agent C
  data/                       # gitignored dumps; A seeds fixtures
    cache/
    fixtures/
  docs/research/              # named specialist files only
  docs/metrics.md             # Agent A
```

| Writable glob | Exclusive owner |
|---------------|-----------------|
| `realtykit/realtykit/**`, `realtykit/pyproject.toml` | Agent A |
| `realtykit/web/**` | Agent B |
| `realtykit/tests/**`, `realtykit/scripts/probes/**` | Agent C |
| `realtykit/docs/research/00-orchestration.md` | Orchestrator / parent |
| `realtykit/docs/research/01-architecture.md` | Architecture specialist |
| `realtykit/docs/research/02-reuse.md` | Reuse specialist (landed) |
| `realtykit/docs/research/03-data-extraction.md` | Data-extraction specialist |
| `realtykit/docs/metrics.md` | Agent A |
| `realtykit/README.md` | Agent A drafts; B adds `web` scripts; C adds test commands — **serialize** by heading |
| `realtykit/data/fixtures/**` | Agent A creates; C copies into `tests/fixtures/` instead of writing here |
| `.gitignore` | Agent A (once) |

**Shared contract rule:** Agent A publishes Pydantic models. Agent B consumes JSON via Vite `/api` proxy → `127.0.0.1:8770`. Agent C asserts schemas. If B needs a field, it files a contract gap — it does not edit `realtykit/realtykit/`.

**Dependency files:** `pyproject.toml` = A; `web/package.json` = B.

**Port:** API **8770** (avoid JobKit 8765). Vite proxies `/api` there.

---

## 5. Definition of done — MVP

A reviewer can, on a laptop with env configured:

1. Start API + frontend from README commands.  
2. See a **map** of US city (or MSA) price **change** and **charts** (price, inventory/DOM or new listings, macro overlay).  
3. Click a city and see updated numbers, not a dead map.  
4. See **freshness** per source; listing/city series claim ≤ 7 days or show **stale**.  
5. See **outlier** listings with reasons.  
6. See **stock dip** metrics for configured tickers and a **correlation** payload (homes × rates × equities) with `insufficient_history` when too short.  
7. `pytest` (C) and at least one probe script pass against local API + fixtures.  
8. No JobKit code, no hardcoded secrets, no second map/chart library.

Out of MVP: auth/SaaS, user accounts, write-back to portals, mobile native apps, nationwide parcel-level coverage.

---

## 6. Exact next spawn list (parent, after specialists return)

Run compile protocol §2, then spawn **three** implementers in parallel with non-overlapping writes:

### Agent A — backend implementer

- **Attach:** `realtykit-data` + `realtykit-analyst`; skill `realtykit-analyze`  
- **Mission:** Ingest adapters, httpx file cache, analysis (correlation, dips, outliers, DOM/inventory), FastAPI + `realtykit serve`  
- **Writes:** `realtykit/realtykit/**`, `realtykit/pyproject.toml`, `realtykit/docs/metrics.md`, `realtykit/data/fixtures/**`, root `.gitignore`  
- **Reads:** all `docs/research/*`, skill, ADR §7  
- **Must ship:** architecture API in §7 (health, freshness, map/cities, kpis, trends, correlation, outliers, stocks/dips, ingest/refresh)  
- **Must not:** `web/**`, `tests/**`, JobKit domain modules, RapidAPI unofficial scrapers, Compass HTML  
- **Sources:** follow `01` §0.1; **confirm with `03`** before coding fetch URLs. Until `03`: Zillow weekly CSVs, FRED `MORTGAGE30US`, Yahoo `^GSPC`, Redfin S3 (label stale), Compass stub `unavailable`, RentCast only if `RENTCAST_API_KEY`  

### Agent B — frontend implementer

- **Attach:** `realtykit-frontend`; skill `realtykit-analyze`  
- **Mission:** React map dashboard (Leaflet choropleth/markers, Recharts, freshness, outliers, city drawer)  
- **Writes:** `realtykit/web/**`  
- **Reads:** fixtures + `/api` from A, research, ADR  
- **Must ship:** Vite app on proxy to `:8770`; map + ≥2 Recharts; dark theme tokens from ADR; stale warning; city click  
- **Must not:** `realtykit/realtykit/**`, `tests/**`, JobKit web copy-paste of apply UI  

### Agent C — test writer

- **Mission:** pytest for analysis + freshness + API contracts; probe scripts for local smoke  
- **Writes:** `realtykit/tests/**`, `realtykit/scripts/probes/**`  
- **Reads:** Pydantic models, fixtures  
- **Must ship:** reject listings without `as_of`; correlation length guard; probe freshness + one city GET  
- **Must not:** `realtykit/realtykit/**` or `web/src/**` (use `tests/fixtures/` copies)  

If A has not created `realtykit/realtykit/` yet, **delay C’s first write** until models exist, or have C test analysis functions A names in `docs/metrics.md`. B may start from fixtures + typed placeholders.

---

## 7. Architecture decision record

**Compiled from:** `01-architecture.md` + `02-reuse.md` + `03-data-extraction.md` (2026-08-31). Live URLs and SLA clocks are locked.

Conflicts resolved by parent (reuse tree + viz-first API from architecture):

| Conflict | Winner | Loser |
|----------|--------|-------|
| API port | **8770** | architecture `:8840` (JobKit is 8765; stay 8770) |
| Map library | **Leaflet + react-leaflet** | architecture MapLibre / react-map-gl (reuse lock; OSM/Carto tiles, no Mapbox token) |
| API paths | **architecture map-first** | generic `/api/cities` + `/api/analysis/*` (keep as aliases if needed) |
| RapidAPI Zillow/Redfin hosts | **out of bounds** (scrapers) | any unofficial listing scrape |
| Compass | **stub `unavailable`** | fake Compass connector |

### Locked

| Decision | Choice | Why |
|----------|--------|-----|
| Product surface | React SPA in `web/` is primary | Canvas has no map/`fetch` |
| API | FastAPI + uvicorn, package `realtykit/` | JobKit **shell** pattern only |
| Serve | `realtykit serve --port 8770` | Avoid JobKit `:8765` |
| UI | React 18 + Vite JSX; proxy `/api` → 8770 | Proven local-first |
| Map | **Leaflet + react-leaflet** (OSM/Carto dark tiles) | No Mapbox token; graduated **city centroids** in MVP |
| Charts | **Recharts only** | One chart lib |
| Theme | Dark tokens (values only) | `#0f0f1a` / `#16162a` / `#4361ee` |
| HTTP | httpx + ETag/Last-Modified + SHA256 file cache | Never load 1GB city/zip into RAM; stream-filter |
| Persist | SQLite `data/realtykit.db` + `data/raw/` | API never reads raw dumps |
| Analysis MVP | stdlib `statistics` + aligned weekly arrays | pandas/yfinance deferred |
| Equities | Yahoo chart API `^GSPC` (optional `^IXIC`) | Stooq blocked |
| Rates | FRED `MORTGAGE30US` CSV (no key required) | Optional `FRED_API_KEY` |
| Auth (local) | Loopback only; no listing-provider keys in the browser | Keys in env on FastAPI process |
| JobKit domain | **None** | No extension, handlers, resume, apply loop |

### Canonical API (from `01`; port 8770)

Every JSON payload includes a `FreshnessBlock`. Unknown fields rejected.

- `GET /api/health`
- `GET /api/freshness`  (alias: `/api/meta/freshness`)
- `GET /api/map/cities`  `GET /api/map/zips`  `GET /api/map/listings`
- `GET /api/kpis`  `GET /api/trends`
- `GET /api/correlation`  `GET /api/outliers`  `GET /api/stocks/dips`
- `POST /api/ingest/refresh`
- `GET /api/auth/bootstrap` (localhost only, optional)

### Sources (live-tested in `03`, 2026-08-31)

Two clocks on every source: `http_last_modified` (file) and `observation_as_of` (inside the file). **Primary 7-day SLA is observation as-of.** Zillow weekly is file-fresh and observation-stale (~16d); banner must say that — do not paint it green.

| Provider | Adapter | MVP posture |
|----------|---------|-------------|
| Zillow weekly inventory / DOM / new listings (metro) | `zillow_research` | **Primary housing.** URLs in `03` §3. Latest week **2026-08-15**, file LM **2026-08-25**. Do not download city ZHVI (93MB) |
| Zillow metro ZHVI monthly | `zillow_research` | Price level + MoM. Latest col **2026-07-31**. Status `by_design_monthly` |
| Redfin national TSV.gz | `redfin_research` | History only. `PERIOD_DURATION=30` only; as-of **2026-05-31**. Skip city/zip/830MB weekly |
| Compass | `compass` stub | Always `unavailable`. Optional `MlsCsvAdapter` later |
| FRED `MORTGAGE30US` | `fred` | **CSV timed out** live. Timeout 8s; optional `FRED_API_KEY`; last-good cache; do not block ingest |
| Yahoo `^GSPC` / `^IXIC` | `yahoo_chart` | **PASS** as-of **2026-08-31**. User-Agent + backoff. No Stooq |
| Census 2024 ZCTA gazetteer | `census_gazetteer` | Centroids. Add a small MSA/CBSA centroid table for metro map pins |
| RentCast listings | `rentcast` | Stub unless `RENTCAST_API_KEY`. No-key MVP = **metro outliers**, empty pin layer |
| RapidAPI unofficial Realtor/Zillow/Redfin/Compass | **none** | Scrapers — do not ship |

Honesty banner copy: housing weeks through **2026-08-15** (published 2026-08-25); stocks through **2026-08-31**; Redfin national through **2026-05**; mortgage rates: live fetch failed until adapter succeeds.

Do not download Redfin objects > 20 MB unless `Last-Modified` moves after 2026-06-02.

### Rejected

- Canvas as the product shell
- Cloning JobKit apply/resume/extension
- Interior Next.js / light theme
- Mapbox GL, MapLibre (this pass), Plotly, D3, yfinance, pandas-for-MVP
- `backend/` + `frontend/` tree
- HTML scrape of Compass / Zillow / Redfin
- Codex Jira/Sentry/SM-ops skills for this product

### Still open (do not block MVP)

- Optional 34 MB Zillow zip weekly inventory for true zip map
- `FRED_API_KEY` / RentCast key from operator
- TypeScript in `web/` (JSX locked)

---

## 8. Security / compliance notes for implementers

- No hardcoded credentials (`REALTYKIT_*` env only).  
- Parameterized data access; structured logs; redact tokens.  
- Validate provider payloads (allow-lists, size limits).  
- Do not ship scrapers designed to bypass access controls.  
- Certificates and vendor TLS: use system trust store; no hardcoded PEM unless a reviewed internal CA file lives outside git secrets.

---

## 9. Parent checklist (copy)

```
- [x] 02-reuse.md read
- [x] 01-architecture.md read; §7 compiled (Leaflet+8770 vs MapLibre+8840)
- [x] 03-data-extraction.md read (live URLs + SLA clocks locked)
- [x] Skill stack table matches §7 (port 8770, Leaflet)
- [x] Spawn A / B / C (2026-08-31, after `03`)
```
