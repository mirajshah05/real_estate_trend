# RealtyKit metrics

All analysis lives in `realtykit/analysis/` and uses the Python stdlib `statistics` module. Constants are only defined in `realtykit/analysis/constants.py`. Copy on charts and API payloads must not imply causation.

## Alignment

Weekly series are joined on the **Friday of the ISO week** (`align.iso_week_key`). Missing observations are dropped. Values are **not** interpolated.

| Series | Transform for correlation |
|--------|---------------------------|
| Housing (inventory or ZHVI) | Week-over-week (or month-over-month) **log return** |
| `^GSPC` | Log return of weekly close |
| `MORTGAGE30US` | First difference (percentage points) |

ZHVI is monthly by design. When a geo has no weekly housing series long enough, correlation falls back to ZHVI returns. Do not invent a weekly ZHVI.

## Correlation

- Statistic: Pearson (`statistics.correlation`) on overlapping aligned points.
- Minimum `n`: **12**. Below that the pair is `insufficient_history`.
- Default window: 104 weeks.
- Pairs: `housing_return × gspc_return`, `housing_return × mortgage_change`, `gspc_return × mortgage_change`.
- Disclaimer (required): *Correlation is not causation. Aligned weekly observations do not imply that housing, equities, or mortgage rates cause each other.*

## Stock dips

For configured tickers (`^GSPC`, `^IXIC`):

| Field | Definition |
|-------|------------|
| `pct_above_52w_low` | `(last − 52w low) / 52w low` |
| `drawdown_52w` | `(last − 52w high) / 52w high` |
| `dip` | `true` if `pct_above_52w_low ≤ 0.05` **or** `drawdown_52w ≤ −0.20` |

These are descriptive flags, not buy signals.

The stock-dip endpoint is a **recent-event scanner**, not an all-history crisis
catalog. It defaults to a 365-day event lookback, evaluates each point against
rolling 52-week highs and lows, and the Yahoo importer currently requests two
years of weekly history. Therefore the 2008 financial crisis is intentionally
outside the current dataset and cannot appear in the dip table.

## Market outliers (MVP)

No listing API in the no-key MVP. Outliers are **metros**, labeled **market outliers**, never “homes.”

Cohort = all metros with a value for the metric in the latest period.

| Metric | Store name |
|--------|------------|
| Inventory week-over-week % | `inventory_wow` |
| Days on market (level) | `days_on_market` |
| ZHVI month-over-month % | `price_change_mom` (`zhvi_mom` query alias) |

`z = (v − mean) / population stdev`. Flag `|z| ≥ 2`. Each row includes `reasons[]`.

## Listing outliers (only when RentCast / MLS exists)

A listing is an outlier if **any** hold (drop rows with missing price or missing geo):

- `price ≥ city median × 2.5` (`HIGH_PRICE_MULT`)
- `price ≤ city median × 0.4` (`LOW_PRICE_MULT`)
- `DOM ≥ city median DOM × 3` (`HIGH_DOM_MULT`) when DOM is present

Always attach `reasons[]`, `as_of`, `source`.

## Freshness

Two clocks on every source:

| Clock | Meaning | SLA |
|-------|---------|-----|
| `http_last_modified` | When the host last wrote the object | Secondary |
| `observation_as_of` | Latest week / period **inside** the file | **Primary 7-day rule** |

Statuses: `live` (daily, ≤24h) · `fresh` (≤7d) · `aging` (8–14d) · `stale` (>14d) · `by_design_monthly` · `unavailable`.

Zillow weekly is typically **file-fresh and observation-stale** (~16 days as of 2026-08-31). That is correct. Do not paint it live. ZHVI is `by_design_monthly`. Compass is always `unavailable`. FRED must not block housing ingest.

## KPI catalog

| KPI | Source | Grain |
|-----|--------|-------|
| Inventory | Zillow weekly metro | week |
| New listings | Zillow weekly metro | week |
| Days on market | Zillow mean days-to-pending | week |
| ZHVI | Zillow metro monthly | month |
| 30y mortgage | FRED `MORTGAGE30US` | week (when fetch works) |
| S&P 500 | Yahoo chart `^GSPC` | day / week |

Probed fixture values (2026-08-31 compile, do not invent replacements): US inventory **1,124,795**, Austin **12,830**, Seattle **12,005** (week **2026-08-15**); ZHVI US **371,774**, Austin **424,339**, Seattle **740,579** (as of **2026-07-31**); `^GSPC` **7,686.14** on **2026-08-31**.
