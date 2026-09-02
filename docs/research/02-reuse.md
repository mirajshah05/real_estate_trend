# RealtyKit Reuse Assessment

**Date:** 2026-08-31  
**Scope:** What existing workspace assets RealtyKit (Real Estate Analyzer) can reuse vs must build greenfield.  
**Explicit exclusion:** JobKit apply-loop, Chrome extension, resume pipeline, Greenhouse/Lever/Ashby handlers.

---

## Executive summary

RealtyKit starts from an **empty git repo** at the repository root. There is **no real-estate, map, or market-data code** anywhere in the workspace today. The highest-value reuse is **architectural**, not domain: JobKit’s **FastAPI + Vite/React + dark-theme SPA + httpx file-cache** stack is a proven local-first pattern. Cursor meta-skills (`create-skill`, `create-rule`, `create-subagent`) should bootstrap RealtyKit-specific agent workflows. **React dashboard is the primary visualization surface**; Cursor Canvas is optional for one-off agent analyses. Interior’s analytics UI offers only CSS bar/table patterns (wrong theme, wrong stack). Codex Jira/Sentry/ops skills are irrelevant unless you later wire enterprise tooling.

---

## 1. RealtyKit current state

| Item | Status |
|------|--------|
| Repo | Initialized git only (`.git/`), no application code |
| `docs/` | Created by this assessment (`docs/research/02-reuse.md`) |
| Dependencies | None |
| `.cursor/` | None yet (should be created under `realtykit/`, not inherited from parent) |

**Verdict:** **Create new** for all product code, skills, rules, and agents scoped to RealtyKit.

---

## 2. JobKit — classification matrix

JobKit path during research: sibling repository `../jobkit`

### 2.1 Reuse as-is

| Asset | Path | Why |
|-------|------|-----|
| Python stack versions | `jobkit/pyproject.toml` | `requires-python >=3.11`, hatchling, ruff/pytest config are copy-ready templates |
| Dev tooling pattern | `jobkit/pyproject.toml` `[project.optional-dependencies] dev` | pytest, ruff, playwright (optional E2E) |
| `.gitignore` ideas | `jobkit/.gitignore` | `data/`, `.venv`, `cache/`, tokens — adapt for `realtykit/data/`, API keys |

Nothing in JobKit’s **domain layer** is reusable as-is for real estate.

### 2.2 Reuse pattern / reimplement

| Asset | Path | Pattern to copy | RealtyKit adaptation |
|-------|------|-----------------|----------------------|
| **FastAPI app shell** | `jobkit/jobkit/api/main.py` | CORS allowlist, bearer token from env or `data/.token`, `/api/health`, `/api/auth/bootstrap` (localhost-only), `Depends(verify_token)` | Same auth model for local dashboard; routes become `/api/markets`, `/api/series`, `/api/geo` |
| **CLI serve** | `jobkit/jobkit/cli.py` | `realtykit serve --port 8765` via uvicorn | New package `realtykit.cli` |
| **Vite + React SPA** | `jobkit/web/` | Minimal React 18, no router initially, single `App.jsx` | Split into map panel + chart panel components |
| **Vite API proxy** | `jobkit/web/vite.config.js` | `proxy: { "/api": "http://127.0.0.1:8765" }` | Same port convention or pick `8770` to avoid collision when both run |
| **Frontend API helper** | `jobkit/web/src/App.jsx` `api()` | Bearer in `localStorage`, bootstrap on 401 | Rename token key to `realtykit_token` |
| **Dark theme CSS** | `jobkit/web/src/index.css` | `#0f0f1a` bg, `#16162a` panels, `#4361ee` accent, table/tag patterns | Extend with map container + chart legend styles |
| **HTTP + file cache** | `jobkit/jobkit/sourcing/cdn.py` | `httpx.AsyncClient`, SHA256 cache keys, TTL via mtime | `MarketDataSourcer` for FRED/Census/Yahoo/etc. |
| **SQLite persistence** | `jobkit/jobkit/ledger/db.py` | stdlib `sqlite3`, explicit schema, JSON columns | Watchlists, saved geographies, ingested snapshots |
| **Pydantic models** | `jobkit/jobkit/models/` | Request/response models, settings | `MarketSeries`, `GeoFeature`, `CorrelationResult` |
| **Project file store** | `jobkit/jobkit/projects/store.py` | Versioned dirs under a root | Optional: saved analysis bundles under `data/analyses/{id}/` |
| **pytest layout** | `jobkit/tests/` | API tests, async httpx test client | Mirror for ingest + API contracts |

### 2.3 Do not reuse

| Asset | Path | Reason |
|-------|------|--------|
| Apply-loop skill | `.cursor/skills/jobkit-apply-loop/SKILL.md` | Job-application automation; user explicitly excluded |
| Apply rule | `.cursor/rules/jobkit-apply.mdc` | Greenhouse/extension/sponsorship constants |
| Chrome extension | `jobkit/extension/` | Form fill/submit — unrelated |
| Handlers | `jobkit/jobkit/handlers/` | ATS schemas (Greenhouse, Lever, Ashby) |
| Resume/tailor/render | `jobkit/jobkit/tailor/`, `render/`, `templates/` | PDF/DOCX resume pipeline |
| Submit/ledger trust | `jobkit/jobkit/submit/`, ledger trust counters | Application trust ladder |
| Profile/essays | `jobkit/jobkit/profile/` | Job application Q&A cache |
| Agent scripts | `jobkit/scripts/agent_apply_*.py`, `apply_automation_loop.py` | Browser apply automation |
| Playwright apply tests | `jobkit/tests/test_ui_playwright.py` (apply flows) | Domain-specific |
| `Projects/default/` | `Project/Projects/default/` | Resume version snapshots (v001–v029) |

---

## 3. Parent workspace `.cursor/` (Project root)

Path during research: parent workspace `../.cursor/`

| Asset | Classification | Notes |
|-------|----------------|-------|
| `skills/jobkit-apply-loop/` | **Do not reuse** | Parent-scoped JobKit skill; RealtyKit needs its own skills under `realtykit/.cursor/skills/` |
| `rules/jobkit-apply.mdc` | **Do not reuse** | Globs `jobkit/**/*`; would not apply to `realtykit/` anyway |

**Recommendation:** Keep parent `.cursor/` untouched. Create **RealtyKit-local** skills/rules so opening the monorepo root does not conflate products.

---

## 4. Cursor built-in skills (`~/.cursor/skills-cursor/`)

| Skill | Classification | Use for RealtyKit |
|-------|----------------|-------------------|
| **create-skill** | **Reuse as-is** | Author `realtykit-analyze-loop`, ingest runbooks |
| **create-rule** | **Reuse as-is** | `.cursor/rules/realtykit-dashboard.mdc` (API keys, data sources, map/chart conventions) |
| **create-subagent** | **Reuse as-is** | Scaffold `.cursor/agents/*.md` (see §8) |
| **canvas** | **Reuse pattern / optional** | Ad-hoc correlation or market briefings beside chat; **not** primary dashboard (no maps, no `fetch`, inline data only, `cursor/canvas` SDK only) |
| **loop** | **Reuse pattern / optional** | Local `/loop 1d refresh market cache` or cloud subscription timer for scheduled ingest |
| **automate** | **Reuse pattern / optional** | Cursor Automation for nightly FRED pull + commit cache (if dashboard-eligible MCPs configured) |
| **sdk** | **Reuse pattern / later** | Only if external scripts call Cursor agents for batch analysis |
| **share** / **new-repo** / **origin** | **Reuse as-is** | Back up `realtykit/` to Cursor-hosted git |
| **review-bugbot** / **review-security** | **Reuse as-is** | PR review after implementation |
| **deploy-with-vercel** | **Reuse pattern / later** | If dashboard is deployed (maps need tile/API keys) |
| **split-to-prs** | **Reuse as-is** | Split ingest vs UI vs analysis PRs |
| **autopilot** | **Reuse as-is** | Keep PR merge-ready |
| **statusline** / **update-cursor-settings** | **Do not reuse** | IDE preference, not product |
| **onboard** / **goal** / **shell** | **Do not reuse** | Generic |

### Canvas vs React dashboard (decision)

| Criterion | React app (primary) | Cursor Canvas (optional) |
|-----------|---------------------|---------------------------|
| Interactive maps (Leaflet) | Yes | No — Canvas SDK has no map primitive |
| Live API data | Yes — via FastAPI proxy | No — embed data inline only |
| Persistent product UX | Yes | Ephemeral chat artifact |
| Multi-panel dashboard | Yes | Single-file analytical snapshot |
| User request | Full-stack app | Agent one-off exploration |

**Verdict:** **React + FastAPI = primary.** Canvas for agent-delivered snapshots (e.g. “compare Case-Shiller vs 10Y yield this week”) when user wants a side panel, not the product shell.

---

## 5. Codex skills (`~/.codex/skills/`)

| Skill | Classification | Notes |
|-------|----------------|-------|
| jira-create-spec / jira-create-plan / jira-implement-subtask / jira-complete | **Do not reuse** (unless PM workflow) | Enterprise Jira orchestration; no Jira context for RealtyKit |
| sentry | **Do not reuse** | No production service yet |
| sm-ops-review | **Do not reuse** | ThousandEyes SM ops; unrelated |
| operational-communication | **Reuse pattern / optional** | Status docs, design proposals |

---

## 6. Sibling projects — maps, charts, dashboards

### 6.1 Interior (sibling repository `../Interior`)

| Finding | Classification |
|---------|----------------|
| Next.js 15 App Router study app | **Do not reuse** (stack mismatch) |
| `src/app/analytics/page.tsx` | **Reuse pattern / weak** — CSS `bar-track`/`bar-fill`, HTML tables; no chart library |
| `globals.css` warm light theme | **Do not reuse** — RealtyKit targets JobKit-like **dark** dashboard |
| No Leaflet/Mapbox/Recharts/D3 | No map/chart code to port |

### 6.2 Jobs_Applier_AI_Agent

Resume/LLM job agent (Python). **Do not reuse.**

### 6.3 MCP-ideation1

Spotify MCP monorepo. **Do not reuse** (no geo/market overlap).

### 6.4 Projects/default

JobKit resume approved versions only. **Do not reuse.**

---

## 7. MCP servers — relevance to RealtyKit

| Namespace | Status | Classification | RealtyKit use |
|-----------|--------|----------------|---------------|
| **cursor-app-control** | Ready | **Reuse as-is** | `move_agent_to_root` → the RealtyKit repository root; `open_resource` for dashboard files |
| **user-github-local** | Ready | **Reuse as-is** | Issues, PRs, repo bootstrap |
| **user-github** | Error (auth) | **Reuse pattern / fix auth** | Same as local once connected |
| **user-atlassian-mcp** | Available | **Do not reuse** (default) | Only if tracking RealtyKit epics in Jira/Confluence |
| **user-slack** | Available | **Reuse pattern / optional** | Alert on threshold (price/rent spread); not core product |
| **user-sentry** | Available | **Do not reuse** (initially) | Post-deploy only |
| **cursor** (GenerateImage) | Available | **Do not reuse** | No image gen in analyzer MVP |
| **Canvas** (via skill) | N/A | **Optional** | Agent-side charts only |

**Note:** Automations skill states only **dashboard-backed** MCP servers work in Cursor Automations. `cursor-app-control` is **not** automation-eligible; use for IDE session control only.

---

## 8. Recommended new Cursor artifacts

### 8.1 Skills (create under `realtykit/.cursor/skills/`)

#### Skill 1: `realtykit-analyze-dashboard` (primary)

**Purpose:** End-to-end workflow for the product dashboard — ingest → API → React map/charts.

**Should include:**
- Dev boot: `realtykit serve --port 8770` + `cd web && npm run dev`
- Data dirs: `data/cache/`, `data/.token`, never commit API keys
- Source allowlist (FRED, Census, public geoJSON, Yahoo chart API vs licensed feeds)
- Correlation analysis steps (align series by date, document methodology in API response)
- When to open React vs spawn a Canvas snapshot

**Classification:** **Create new** (pattern from `jobkit-apply-loop` structure only — phases, commands table — not content)

#### Skill 2: `realtykit-data-ingest` (optional split)

**Purpose:** Agent-run ingest refresh, cache invalidation, schema validation.

**Classification:** **Create new**

#### Skill 3: `realtykit-market-brief-canvas` (optional)

**Purpose:** When user asks for a **one-off** comparison in chat, build a `.canvas.tsx` under workspace `canvases/` with inline fetched summary (agent pre-computes numbers; Canvas does not fetch).

**Classification:** **Create new**

### 8.2 Rules (`.cursor/rules/`)

| Rule file | Globs | Classification |
|-----------|-------|----------------|
| `realtykit-core.mdc` | `realtykit/**/*` | **Create new** — product identity, no JobKit imports, local-first |
| `realtykit-api.mdc` | `realtykit/**/api/**/*.py` | **Create new** — pydantic contracts, httpx timeouts, cache keys |
| `realtykit-web.mdc` | `realtykit/web/**/*.{jsx,tsx,css}` | **Create new** — dark theme tokens, map/chart component boundaries |

Do **not** copy `jobkit-apply.mdc`.

### 8.3 Subagents (`.cursor/agents/`)

Per `create-subagent` skill format (`name` + `description` + system prompt body):

| Subagent | Description trigger | Responsibilities |
|----------|----------------------|------------------|
| **`realtykit-data-ingest`** | Fetch/cache market series, geoJSON, validate schemas | httpx clients, cache TTL, pydantic models, pytest for parsers; no UI |
| **`realtykit-map-ui`** | Leaflet layers, choropleth, markers, geoJSON styling | React-Leaflet, tile attribution, responsive layout, dark map tiles |
| **`realtykit-correlation-analyst`** | Statistical joins, trend comparison, spread metrics | Date alignment, correlation/regression, API endpoints returning analysis JSON; document assumptions |

Optional fourth: **`realtykit-api-reviewer`** — FastAPI route review, auth, CORS (proactive after API changes).

**Classification:** **Create new** for all four.

---

## 9. Python / JavaScript libraries

### 9.1 Adopt (from JobKit pattern + product needs)

| Library | Source | Role |
|---------|--------|------|
| **fastapi** | JobKit pyproject | API layer |
| **uvicorn[standard]** | JobKit | Dev server |
| **httpx** | JobKit | Async external API fetch |
| **pydantic** / **pydantic-settings** | JobKit | Models + config |
| **pyyaml** | JobKit | Optional market config manifests |
| **aiofiles** | JobKit | Async cache writes |
| **react** / **react-dom** | JobKit web | UI |
| **vite** / **@vitejs/plugin-react** | JobKit web | Bundler |
| **react-leaflet** + **leaflet** | New | Maps (primary viz) |
| **recharts** | New | Time-series / multi-series charts in dashboard |

### 9.2 Defer or avoid (initial MVP)

| Library | Verdict | Rationale |
|---------|---------|-----------|
| **yfinance** | **Avoid initially** | Adds dependency and scraping fragility; prefer direct Yahoo chart/quote HTTP endpoints or FRED/Census via httpx until requirements prove otherwise |
| **pandas** | **Defer** | Use stdlib `csv`, `json`, `datetime`, list/dict joins for MVP ingest; add pandas when rolling windows, resampling, or large joins become painful |
| **numpy** / **scipy** | **Defer** | Add with correlation subagent when beyond Pearson on aligned arrays |
| **mapbox-gl** | **Defer** | Leaflet + OSM/Carto dark tiles sufficient for local analyzer; Mapbox needs token + billing |
| **plotly** / **d3** | **Avoid** | Recharts covers dashboard charts; lighter bundle |
| **python-docx**, **PyMuPDF**, **pdf2docx** | **Do not add** | JobKit resume stack |
| **playwright** | **Optional dev** | E2E dashboard smoke tests only, not apply automation |

### 9.3 Stdlib-first ingest (recommended MVP)

- `sqlite3` — snapshot metadata (pattern from JobKit ledger)
- `csv` / `json` — parse FRED/Census exports
- `hashlib` — cache keys (pattern from `JobSourcer._cache_path`)
- `statistics` — mean, stdev, correlation for simple analysis

---

## 10. Suggested RealtyKit monorepo layout (greenfield)

Pattern-only derivation from JobKit; **not implemented**:

```
realtykit/
├── pyproject.toml
├── realtykit/
│   ├── api/main.py          # FastAPI (auth, markets, geo, analysis)
│   ├── cli.py               # serve command
│   ├── ingest/              # httpx fetchers + cache
│   ├── models/              # pydantic
│   ├── store/               # sqlite + file cache
│   └── analysis/            # correlation, spreads
├── web/                     # Vite + React dashboard
│   ├── src/
│   │   ├── App.jsx
│   │   ├── MapPanel.jsx
│   │   └── TrendCharts.jsx
│   └── vite.config.js
├── data/
│   ├── cache/
│   └── .token
├── tests/
├── docs/research/
└── .cursor/
    ├── skills/realtykit-analyze-dashboard/
    ├── rules/realtykit-core.mdc
    └── agents/
        ├── realtykit-data-ingest.md
        ├── realtykit-map-ui.md
        └── realtykit-correlation-analyst.md
```

---

## 11. JobKit web/API pattern reference (for implementers)

### Auth flow (copy pattern)

1. Server writes bearer token to `data/.token` on startup.
2. `GET /api/auth/bootstrap` returns token on localhost only.
3. SPA stores token in `localStorage`, sends `Authorization: Bearer …` on `/api/*`.
4. Vite dev server proxies `/api` → FastAPI.

### Dark theme tokens (copy from JobKit)

- Background: `#0f0f1a`
- Panel: `#16162a`
- Header: `#1a1a2e`
- Accent/button: `#4361ee`
- Success/warn/error: `#4ade80` / `#fcd34d` / `#f87171`

### HTTP cache pattern (adapt from `JobSourcer`)

- Cache path: `hashlib.sha256(url).hexdigest()[:16].json`
- TTL: file mtime (e.g. 24h index, 1h series)
- gzip support for bulk downloads

---

## 12. Summary classification table

| Category | Reuse as-is | Reuse pattern | Do not reuse | Create new |
|----------|-------------|---------------|--------------|------------|
| JobKit Python deps | pyproject template | fastapi, httpx, pydantic, uvicorn | resume, handlers, extension | ingest, analysis, geo models |
| JobKit web | — | vite proxy, dark CSS, api() helper | gap analysis UI, PDF views | map + recharts dashboard |
| JobKit data | — | sqlite ledger, file cache, ProjectStore idea | ledger trust, profile.json | market cache, watchlists |
| `.cursor` parent | — | — | jobkit-apply-loop, jobkit-apply.mdc | realtykit skills, rules, agents |
| skills-cursor | create-*, share, review-* | canvas, loop, automate | onboard, shell | realtykit-analyze-dashboard |
| Codex skills | — | operational-communication | jira, sentry, sm-ops | — |
| Interior | — | CSS bar/table (weak) | Next.js app, light theme | — |
| Other siblings | — | — | Jobs_Applier, MCP-ideation1, Projects/default | — |
| MCP | cursor-app-control, github-local | slack (alerts) | atlassian, sentry (MVP) | — |
| Viz surface | — | Canvas for ad-hoc | Canvas as primary | React SPA primary |
| Libraries | fastapi, httpx, react, vite | — | yfinance, pandas (MVP), mapbox | leaflet, recharts |

---

## 13. Next steps (research only — not implementation)

1. Add `realtykit/.cursor/skills/realtykit-analyze-dashboard/SKILL.md` using **create-skill**.
2. Add three subagents under `realtykit/.cursor/agents/`.
3. Scaffold `pyproject.toml` + `web/package.json` mirroring JobKit versions, adding leaflet + recharts.
4. Document data source contracts in `docs/research/03-data-sources.md` (separate task).
5. Use **share** or **new-repo** when ready to back up RealtyKit to Cursor git.

---

*Assessment performed against workspace state on 2026-08-31. JobKit referenced at sibling path; no code was copied.*
