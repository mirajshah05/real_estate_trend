/** Coerce API payloads. Missing fields become null — never invented market numbers. */

export function asNumber(value) {
  if (value == null || value === "") return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function asText(value) {
  if (value == null) return "";
  return String(value);
}

export function asDateText(value) {
  if (!value) return null;
  const s = String(value);
  const iso = s.match(/^(\d{4}-\d{2}-\d{2})/);
  if (iso) return iso[1];
  const parsed = new Date(s);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed.toISOString().slice(0, 10);
  }
  return s;
}

export function daysSince(isoDate, now = new Date()) {
  const d = asDateText(isoDate);
  if (!d) return null;
  const then = new Date(`${d}T00:00:00Z`);
  if (Number.isNaN(then.getTime())) return null;
  return Math.floor((now.getTime() - then.getTime()) / 86400000);
}

export function pickKpi(block, keys) {
  if (!block) return null;
  const kpis = block.kpis || block;
  for (const key of keys) {
    if (kpis[key] != null) return kpis[key];
  }
  return null;
}

export function kpiValue(entry) {
  if (entry == null) return null;
  if (typeof entry === "number") return asNumber(entry);
  return asNumber(entry.value);
}

export function kpiDelta(entry, which) {
  if (entry == null || typeof entry !== "object") return null;
  return asNumber(entry[which] ?? entry[`delta_${which}`]);
}

export function normalizeCities(payload) {
  const list = (payload && (payload.features || payload.cities || payload.metros)) || [];
  return list
    .map((f) => ({
      geo_id: asText(f.geo_id || f.id || f.region_id),
      name: asText(f.name || f.region || f.RegionName),
      state: asText(f.state || f.state_code || ""),
      lat: asNumber(f.lat ?? f.latitude),
      lon: asNumber(f.lon ?? f.lng ?? f.longitude),
      value: asNumber(f.value),
      price_change_yoy: asNumber(f.price_change_yoy ?? f.yoy ?? f.zhvi_yoy),
      price_change_mom: asNumber(f.price_change_mom ?? f.mom ?? f.zhvi_mom),
      inventory: asNumber(f.inventory),
      inventory_change: asNumber(
        f.inventory_change ?? f.inventory_delta ?? f.inventory_wow ?? f.inventory_yoy
      ),
      days_on_market: asNumber(f.days_on_market ?? f.dom ?? f.median_dom),
      new_listings: asNumber(f.new_listings),
      typical_value: asNumber(f.typical_value ?? f.zhvi ?? f.price ?? f.median_list_price),
      is_outlier: Boolean(f.is_outlier || f.outlier),
      kind: asText(f.kind || "geo"),
      label: asText(f.label || ""),
      market_geo_id: asText(f.market_geo_id || ""),
    }))
    .filter((f) => f.lat != null && f.lon != null);
}

export function normalizeGovernmentAreas(payload) {
  const list = (payload && payload.features) || [];
  return list
    .map((feature) => ({
      area_id: asText(feature.area_id),
      geo_id: asText(feature.area_id),
      name: asText(feature.name),
      state: asText(feature.state),
      county: asText(feature.county),
      lat: asNumber(feature.lat),
      lon: asNumber(feature.lon),
      parcel_count: asNumber(feature.parcel_count),
      geometry: feature.geometry || null,
      kind: "city",
      market_geo_id: asText(feature.parent_geo_id),
      source_id: asText(feature.source_id),
      observation_as_of: asDateText(feature.observation_as_of),
      fetched_at: asDateText(feature.fetched_at),
      note: asText(feature.note),
    }))
    .filter((feature) => feature.geometry && feature.lat != null && feature.lon != null);
}

export function cityMetric(feature, metric) {
  if (metric === "price_change_mom") {
    return feature.price_change_mom;
  }
  if (metric === "inventory_change") {
    return feature.inventory_change;
  }
  return feature.price_change_yoy ?? feature.value;
}

export function normalizeSeries(raw) {
  if (!raw) return [];
  if (!Array.isArray(raw)) return [];
  return raw
    .map((p) => ({
      t: asDateText(p.t || p.date || p.period_end || p.ts || p.week),
      v: asNumber(p.v ?? p.value ?? p.close ?? p.y),
    }))
    .filter((p) => p.t && p.v != null);
}

export function normalizeTrends(payload) {
  const series = (payload && payload.series) || {};
  const keys = Object.keys(series);
  const out = {};
  for (const key of keys) {
    out[key] = normalizeSeries(series[key]);
  }
  return {
    geo_id: payload && payload.geo_id,
    cadence: payload && payload.cadence,
    series: out,
    freshness: payload && payload.freshness,
  };
}

export function mergeSeries(named) {
  const byT = new Map();
  for (const [name, points] of Object.entries(named)) {
    for (const p of points) {
      if (!byT.has(p.t)) byT.set(p.t, { t: p.t });
      byT.get(p.t)[name] = p.v;
    }
  }
  return Array.from(byT.values()).sort((a, b) => (a.t < b.t ? -1 : 1));
}

export function normalizeUnitInterval(points) {
  if (!points.length) return [];
  const vs = points.map((p) => p.v);
  const lo = Math.min(...vs);
  const hi = Math.max(...vs);
  const span = hi - lo || 1;
  return points.map((p) => ({ t: p.t, v: (p.v - lo) / span }));
}

export function summarizeSeries(points) {
  const ordered = (points || [])
    .filter((p) => p && p.t && Number.isFinite(p.v))
    .slice()
    .sort((a, b) => (a.t < b.t ? -1 : a.t > b.t ? 1 : 0));
  if (!ordered.length) return null;

  const values = ordered.map((p) => p.v);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = high - low || 1;
  const first = ordered[0];
  const latest = ordered[ordered.length - 1];
  return {
    count: ordered.length,
    start: first,
    latest,
    low,
    high,
    change: latest.v - first.v,
    changePct: first.v ? ((latest.v - first.v) / Math.abs(first.v)) * 100 : null,
    rangePosition: ((latest.v - low) / span) * 100,
  };
}

export function normalizeOutliers(payload) {
  const rows = (payload && (payload.rows || payload.outliers)) || [];
  const block = payload && payload.freshness;
  const fallbackAsOf = asDateText(
    (payload && payload.as_of) || (block && (block.observation_as_of || block.as_of))
  );
  const fallbackSource = asText(
    (payload && payload.provider) || (block && (block.source || block.provider)) || ""
  );
  return rows.map((r) => ({
    subject_id: asText(r.subject_id || r.geo_id || r.id),
    name: asText(r.name || r.subject_id || "Unknown metro"),
    score: asNumber(r.score),
    value: asNumber(r.value),
    cohort_median: asNumber(r.cohort_median),
    reasons: Array.isArray(r.reasons) ? r.reasons.map(asText) : [],
    as_of: asDateText(r.as_of) || fallbackAsOf,
    source: asText(r.source || r.provider || fallbackSource),
  }));
}

export function normalizeDips(payload) {
  const dips = (payload && payload.dips) || [];
  return {
    symbol: (payload && payload.symbol) || "^GSPC",
    lookback_days: asNumber(payload && payload.lookback_days),
    threshold_window_weeks: asNumber(payload && payload.threshold_window_weeks),
    event_window_start: asDateText(payload && payload.event_window_start),
    history_start: asDateText(payload && payload.history_start),
    history_end: asDateText(payload && payload.history_end),
    history_points: asNumber(payload && payload.history_points),
    note: asText(payload && payload.note),
    last: payload && payload.last
      ? {
          t: asDateText(payload.last.t),
          close: asNumber(payload.last.close),
          drawdown_52w: asNumber(payload.last.drawdown_52w),
        }
      : null,
    dips: dips.map((d) => ({
      t: asDateText(d.t),
      close: asNumber(d.close),
      kind: asText(d.kind || "drawdown"),
      from_peak: asNumber(d.from_peak),
      peak_t: asDateText(d.peak_t),
    })),
    freshness: payload && payload.freshness,
  };
}

export function normalizeCorrelation(payload) {
  const pairs = (payload && payload.pairs) || [];
  const best = (payload && payload.best_lags) || [];
  return {
    n: asNumber(payload && payload.n),
    aligned_cadence: (payload && payload.aligned_cadence) || null,
    pairs: pairs.map((p) => ({
      a: asText(p.a),
      b: asText(p.b),
      lag_weeks: asNumber(p.lag_weeks),
      pearson: asNumber(p.pearson),
      spearman: asNumber(p.spearman),
    })),
    best_lags: best.map((p) => ({
      a: asText(p.a),
      b: asText(p.b),
      lag_weeks: asNumber(p.lag_weeks),
      pearson: asNumber(p.pearson),
      note: asText(p.note),
    })),
    disclaimer:
      (payload && payload.disclaimer) ||
      "Correlation is not causation.",
    insufficient: Boolean(payload && payload.insufficient_history),
    freshness: payload && payload.freshness,
  };
}

export function normalizeListings(payload) {
  const list = (payload && payload.listings) || [];
  return list
    .map((l) => ({
      listing_id: asText(l.listing_id || l.id),
      address: asText(l.address || l.formattedAddress),
      city: asText(l.city),
      state: asText(l.state),
      zip_code: asText(l.zip_code || l.zipCode),
      property_type: asText(l.property_type || l.propertyType),
      lat: asNumber(l.lat),
      lon: asNumber(l.lon ?? l.lng),
      price: asNumber(l.price),
      beds: asNumber(l.beds),
      baths: asNumber(l.baths),
      sqft: asNumber(l.sqft),
      dom: asNumber(l.dom),
      status: asText(l.status),
      as_of: asDateText(l.as_of || l.listed_at),
      outlier_score: asNumber(l.outlier_score),
      outlier_reasons: Array.isArray(l.outlier_reasons)
        ? l.outlier_reasons.map(asText)
        : [],
      photos: (Array.isArray(l.photos) ? l.photos : Array.isArray(l.images) ? l.images : [])
        .map((photo) => asText(typeof photo === "string" ? photo : photo && (photo.url || photo.href)))
        .filter(Boolean),
    }))
    .filter((l) => l.lat != null && l.lon != null);
}

/** Flatten rental trend payloads while accepting both row and grouped-series APIs. */
export function normalizeRentalTrends(payload) {
  if (!payload) return { rows: [], market_indices: [], as_of: null, summary: null };
  const rows = [];
  const add = (point, group = {}) => {
    const month = asDateText(
      point.month || point.period || point.period_end || point.observed_on || point.date || point.t
    );
    const rent = asNumber(
      point.median_rent ?? point.monthly_rent ?? point.rent ?? point.value ?? point.v
    );
    if (!month || rent == null) return;
    rows.push({
      month: month.slice(0, 7),
      city: asText(point.city || group.city || payload.city),
      bedrooms: asNumber(point.bedrooms ?? point.beds ?? group.bedrooms ?? group.beds),
      property_type: asText(
        point.property_type || point.propertyType || group.property_type || group.propertyType || "All homes"
      ),
      listing_status: asText(point.listing_status || point.status || group.listing_status),
      median_rent: rent,
      average_rent: asNumber(point.average_rent ?? point.mean_rent),
      count: asNumber(point.count ?? point.listing_count ?? point.sample_size),
    });
  };

  const direct = payload.rows || payload.trends || payload.data || payload.segments;
  if (Array.isArray(direct)) direct.forEach((row) => add(row));

  const series = payload.series;
  if (Array.isArray(series)) {
    series.forEach((group) => {
      const points = group.points || group.values || group.data;
      if (Array.isArray(points)) points.forEach((point) => add(point, group));
      else add(group);
    });
  } else if (series && typeof series === "object") {
    Object.entries(series).forEach(([key, value]) => {
      if (!Array.isArray(value)) return;
      const bedMatch = key.match(/(?:^|\D)([1-3])\s*(?:bed|br|bd)?/i);
      const typeMatch = key.match(/apartment|townhouse|single[_ -]?family/i);
      value.forEach((point) => add(point, {
        bedrooms: bedMatch ? Number(bedMatch[1]) : null,
        property_type: typeMatch ? typeMatch[0].replace(/[_-]/g, " ") : "All homes",
      }));
    });
  }

  const marketIndices = Array.isArray(payload.market_indices)
    ? payload.market_indices.map((index) => ({
        provider: asText(index.provider),
        source_id: asText(index.source_id),
        metric: asText(index.metric),
        home_type: asText(index.home_type),
        city: asText(index.city || payload.city),
        as_of: asDateText(index.as_of),
        points: Array.isArray(index.points)
          ? index.points.map((point) => ({
              month: asDateText(point.month || point.period_end || point.t)?.slice(0, 7),
              value: asNumber(point.value ?? point.v),
            })).filter((point) => point.month && point.value != null)
          : [],
      }))
    : [];

  return {
    rows: rows.sort((a, b) => a.month.localeCompare(b.month)),
    market_indices: marketIndices,
    rentcast_usage: payload.rentcast_usage || null,
    observation_count: asNumber(payload.observation_count) || 0,
    first_observed_on: asDateText(payload.first_observed_on),
    last_observed_on: asDateText(payload.last_observed_on),
    as_of: asDateText(payload.as_of || payload.last_observed_on || payload.date_to || payload.observation_as_of),
    date_from: asDateText(payload.date_from),
    date_to: asDateText(payload.date_to),
    summary: payload.summary || payload.coverage || null,
  };
}

export function normalizeSales(payload) {
  const list = (payload && payload.sales) || [];
  return list
    .map((s) => ({
      event_id: asText(s.event_id || s.id),
      property_id: asText(s.property_id),
      provider: asText(s.provider),
      address: asText(s.address),
      city: asText(s.city),
      state: asText(s.state),
      zip_code: asText(s.zip_code),
      lat: asNumber(s.lat),
      lon: asNumber(s.lon),
      sale_date: asDateText(s.sale_date),
      price: asNumber(s.price),
      property_type: asText(s.property_type),
      beds: asNumber(s.beds),
      baths: asNumber(s.baths),
      sqft: asNumber(s.sqft),
      fetched_at: asText(s.fetched_at),
      record_origin: asText(s.record_origin),
    }))
    .filter((s) => s.event_id && s.lat != null && s.lon != null);
}

const WEEKLY_HINT = /zillow|inventory|dom|listing|housing/i;
const STOCK_HINT = /yahoo|gspc|ixic|equity|stock/i;
const RATE_HINT = /fred|mortgage|rate/i;
const REDFIN_HINT = /redfin/i;
const COMPASS_HINT = /compass/i;

export function displayStatus(source, now = new Date()) {
  if (!source) return "unavailable";
  const raw = source.status || source.freshness || "";
  if (raw === "unavailable") return "unavailable";
  if (raw === "by_design_monthly") return "by_design_monthly";

  const asOf = asDateText(source.as_of || source.observation_as_of);
  const days = daysSince(asOf, now);
  const cadence = source.cadence || "";
  const weekly =
    cadence === "weekly" || WEEKLY_HINT.test(`${source.dataset || ""} ${source.provider || ""}`);
  const daily = cadence === "daily" || STOCK_HINT.test(`${source.dataset || ""} ${source.provider || ""}`);

  if (days != null) {
    if (weekly) {
      if (days > 14) return "stale";
      if (days > 7) return "aging";
      return "fresh";
    }
    if (daily) {
      if (days <= 1) return "live";
      if (days <= 7) return "fresh";
      if (days <= 14) return "aging";
      return "stale";
    }
    if (cadence === "monthly" || raw === "by_design_monthly") return "by_design_monthly";
    if (days > 14) return "stale";
    if (days > 7) return "aging";
  }

  if (raw === "live" && weekly) return days != null && days > 7 ? "aging" : "fresh";
  return raw || "unavailable";
}

export function freshnessSources(payload) {
  const block = payload && (payload.freshness || payload);
  const sources = (block && block.sources) || [];
  return sources.map((s) => ({
    source_id: asText(s.source_id || s.source),
    provider: asText(s.provider),
    dataset: asText(s.dataset),
    as_of: asDateText(s.as_of || s.observation_as_of),
    fetched_at: asDateText(s.fetched_at),
    http_last_modified: asDateText(s.http_last_modified || s.file_date),
    cadence: s.cadence || "unknown",
    status: displayStatus(s),
    note: asText(s.note),
  }));
}

/**
 * Honesty line. Prefer live ledger dates. If the API is down, use the
 * research-locked copy from 03-data-extraction.md §8 — dates, not prices.
 */
export const RESEARCH_HONESTY =
  "Housing weeks through 2026-08-15 (published 2026-08-25). Stocks through 2026-08-31. Redfin national through 2026-05. Mortgage rates: live fetch failed.";

export function honestySummary(payload, apiOnline) {
  if (payload && payload.goal && payload.goal.honest_summary) {
    return payload.goal.honest_summary;
  }
  const sources = freshnessSources(payload);
  if (!sources.length) {
    return RESEARCH_HONESTY;
  }

  const zillow = sources.find((s) => /zillow/i.test(s.provider) && /week|inv|dom|list/i.test(s.dataset || s.source_id));
  const zhvi = sources.find((s) => /zhvi|zillow/i.test(`${s.provider} ${s.dataset}`) && s.cadence === "monthly");
  const stocks = sources.find((s) => STOCK_HINT.test(`${s.provider} ${s.dataset} ${s.source_id}`));
  const redfin = sources.find((s) => REDFIN_HINT.test(s.provider));
  const rates = sources.find((s) => RATE_HINT.test(`${s.provider} ${s.dataset} ${s.source_id}`));

  const parts = [];
  if (zillow && zillow.as_of) {
    const pub = zillow.http_last_modified ? ` (published ${zillow.http_last_modified})` : "";
    parts.push(`Housing weeks through ${zillow.as_of}${pub}`);
  } else if (zhvi && zhvi.as_of) {
    parts.push(`Housing index through ${zhvi.as_of} (monthly)`);
  } else {
    parts.push("Housing weeks through 2026-08-15 (published 2026-08-25)");
  }

  if (stocks && stocks.as_of) {
    parts.push(`stocks through ${stocks.as_of}`);
  } else if (apiOnline) {
    parts.push("stocks as reported by Yahoo");
  } else {
    parts.push("stocks through 2026-08-31");
  }

  if (redfin && redfin.as_of) {
    parts.push(`Redfin national through ${redfin.as_of.slice(0, 7)}`);
  } else {
    parts.push("Redfin national through 2026-05");
  }

  if (!rates || rates.status === "unavailable" || !rates.as_of) {
    parts.push("mortgage rates unavailable");
  } else {
    parts.push(`mortgage rates through ${rates.as_of}`);
  }

  return `${parts[0]}. ${parts.slice(1).join("; ")}.`;
}

export const CANONICAL_SOURCES = [
  { id: "zillow", provider: "Zillow Research", match: /zillow/i },
  { id: "redfin", provider: "Redfin", match: REDFIN_HINT, defaultStatus: "stale" },
  { id: "compass", provider: "Compass", match: COMPASS_HINT, defaultStatus: "unavailable" },
  { id: "yahoo", provider: "Yahoo", match: STOCK_HINT },
  { id: "fred", provider: "FRED", match: RATE_HINT },
  {
    id: "government",
    provider: "County GIS",
    match: /government|santa clara|san mateo/i,
    prefer: /santa_clara_public_parcel/i,
  },
];

/** Dates from 03-data-extraction.md §8 — not live prices. */
const RESEARCH_CHIP_DEFAULTS = {
  zillow: {
    as_of: "2026-08-15",
    file_date: "2026-08-25",
    status: "aging",
    note: "Weekly obs 16d old vs 2026-08-31. File published 2026-08-25. Not live.",
  },
  redfin: {
    as_of: "2026-05-31",
    file_date: "2026-06-02",
    status: "stale",
    note: "National tracker through 2026-05. Historical only.",
  },
  compass: {
    as_of: null,
    file_date: null,
    status: "unavailable",
    note: "No official API. Not scraped.",
  },
  yahoo: {
    as_of: "2026-08-31",
    file_date: null,
    status: "live",
    note: "Last research probe close date. Confirm via /api/stocks/dips.",
  },
  fred: {
    as_of: null,
    file_date: null,
    status: "unavailable",
    note: "Mortgage rates: live fetch failed.",
  },
  government: {
    as_of: null,
    file_date: null,
    status: "unavailable",
    note: "Refresh to download official Santa Clara and San Mateo GIS reference snapshots.",
  },
};

export function sourcesPanelRows(payload) {
  const live = freshnessSources(payload);
  return CANONICAL_SOURCES.map((canon) => {
    const candidates = live.filter((s) =>
      canon.match.test(`${s.provider} ${s.dataset} ${s.source_id}`)
    );
    const hit =
      (canon.prefer && candidates.find((s) => canon.prefer.test(`${s.dataset} ${s.source_id}`))) ||
      candidates[0];
    if (hit) {
      return {
        id: canon.id,
        provider: canon.provider,
        dataset: hit.dataset,
        as_of: hit.as_of,
        file_date: hit.http_last_modified,
        status: hit.status,
        note: hit.note,
      };
    }
    const fallback = RESEARCH_CHIP_DEFAULTS[canon.id] || {};
    return {
      id: canon.id,
      provider: canon.provider,
      dataset: "",
      as_of: fallback.as_of || null,
      file_date: fallback.file_date || null,
      status: fallback.status || canon.defaultStatus || "unavailable",
      note: fallback.note || "",
    };
  });
}

export function formatCompact(n) {
  if (n == null) return "—";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `${Math.round(n / 1000)}k`;
  if (abs >= 1000) return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (abs >= 100) return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (Number.isInteger(n)) return String(n);
  return n.toLocaleString("en-US", { maximumFractionDigits: 1 });
}

export function formatMoney(n) {
  if (n == null) return "—";
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function formatPct(n, digits = 1) {
  if (n == null) return "—";
  const pct = Math.abs(n) <= 2 ? n * 100 : n;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}

export function formatSigned(n, digits = 2) {
  if (n == null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}`;
}

export function nationalGeoId(cities) {
  const us = cities.find((c) => /united states|^us$|nation/i.test(`${c.name} ${c.geo_id}`));
  if (us) return us.geo_id;
  return "nation:US";
}
