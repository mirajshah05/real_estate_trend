import { mergeSeries, normalizeUnitInterval } from "./normalize.js";

export const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const OVERLAY_DEFINITIONS = [
  {
    key: "housing",
    label: "Home value",
    color: "#4361ee",
    source: "Zillow ZHVI",
    cadence: "monthly",
    kind: "money",
    description: "Estimated typical home value in this area",
    seriesKeys: ["zhvi", "typical_value", "median_list_price", "home_value"],
  },
  {
    key: "gspc",
    label: "S&P 500",
    color: "#e8e8f0",
    source: "Yahoo Finance ^GSPC",
    cadence: "weekly",
    kind: "index",
    description: "National stock-market index",
    seriesKeys: ["gspc", "GSPC", "spx", "^GSPC"],
  },
  {
    key: "mortgage",
    label: "Mortgage rate",
    color: "#c9a227",
    source: "FRED MORTGAGE30US",
    cadence: "weekly",
    kind: "rate",
    description: "National average 30-year mortgage rate",
    seriesKeys: ["mortgage_30y", "MORTGAGE30US", "mortgage", "rates"],
  },
];

function finite(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function paddedMoneyDomain(values, minimumSpan = 200) {
  const numbers = values.filter(finite);
  if (!numbers.length) return [0, minimumSpan];
  const low = Math.min(...numbers);
  const high = Math.max(...numbers);
  const span = Math.max(high - low, minimumSpan);
  const center = (low + high) / 2;
  const padding = span * 0.12;
  const step = span >= 1000 ? 100 : 50;
  const floor = Math.max(0, Math.floor((center - span / 2 - padding) / step) * step);
  const ceiling = Math.ceil((center + span / 2 + padding) / step) * step;
  return ceiling > floor ? [floor, ceiling] : [Math.max(0, floor - step), ceiling + step];
}

export function monthKeysBetween(start, end) {
  if (!start || !end) return [];
  const first = String(start).slice(0, 7).split("-").map(Number);
  const last = String(end).slice(0, 7).split("-").map(Number);
  if (first.length !== 2 || last.length !== 2 || first.some(Number.isNaN) || last.some(Number.isNaN)) return [];
  const keys = [];
  let index = first[0] * 12 + first[1] - 1;
  const finalIndex = last[0] * 12 + last[1] - 1;
  while (index <= finalIndex && keys.length < 36) {
    keys.push(`${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`);
    index += 1;
  }
  return keys;
}

export function canonicalRentalType(value) {
  const raw = String(value || "").toLowerCase().replace(/[_-]/g, " ");
  if (raw.includes("apartment")) return "Apartment";
  if (raw.includes("town")) return "Townhouse";
  if (raw.includes("single") || raw === "house") return "Single Family";
  return "All";
}

export function canonicalRentalStatus(value) {
  const raw = String(value || "").toLowerCase();
  if (raw.includes("new")) return "New";
  if (raw.includes("exist") || raw.includes("old") || raw.includes("active")) return "Existing";
  return "All";
}

export function buildRentalChartRows({ rows, dateFrom, dateTo, propertyType, listingStatus }) {
  const showingAverage = propertyType === "All" || listingStatus === "All";
  const monthly = new Map(monthKeysBetween(dateFrom, dateTo).map((month) => [month, { month }]));
  (rows || []).forEach((row) => {
    if (propertyType !== "All" && canonicalRentalType(row.property_type) !== propertyType) return;
    if (listingStatus !== "All" && canonicalRentalStatus(row.listing_status) !== listingStatus) return;
    const bed = Number(row.bedrooms);
    if (![1, 2, 3].includes(bed)) return;
    if (!monthly.has(row.month)) monthly.set(row.month, { month: row.month });
    const target = monthly.get(row.month);
    const weight = row.count == null ? 1 : Math.max(1, row.count);
    const value = showingAverage ? (row.average_rent ?? row.median_rent) : row.median_rent;
    if (!finite(value)) return;
    target[`sum${bed}`] = (target[`sum${bed}`] || 0) + value * weight;
    target[`count${bed}`] = (target[`count${bed}`] || 0) + weight;
  });
  return Array.from(monthly.values()).map((row) => {
    [1, 2, 3].forEach((bed) => {
      if (row[`count${bed}`]) row[`bed${bed}`] = Math.round(row[`sum${bed}`] / row[`count${bed}`]);
      delete row[`sum${bed}`];
    });
    return row;
  }).sort((a, b) => a.month.localeCompare(b.month));
}

export function rentalPointRadius(chartRows) {
  const observedMonths = (chartRows || []).filter((row) =>
    [1, 2, 3].some((bed) => finite(row[`bed${bed}`]))
  ).length;
  return observedMonths <= 2 ? 4 : 2;
}

export function selectCityMarketIndex(indices, city) {
  const target = String(city || "").trim().toLowerCase();
  return (indices || []).find(
    (index) => String(index.city || "").trim().toLowerCase() === target && index.points?.length
  ) || null;
}

export function rentalSeasonality(points) {
  const clean = (points || [])
    .filter((point) => /^\d{4}-\d{2}$/.test(point.month || "") && finite(point.value))
    .slice()
    .sort((a, b) => a.month.localeCompare(b.month));
  if (!clean.length) return null;

  const byYear = new Map();
  clean.forEach((point) => {
    const year = Number(point.month.slice(0, 4));
    const month = Number(point.month.slice(5, 7));
    if (!byYear.has(year)) byYear.set(year, []);
    byYear.get(year).push({ ...point, year, month });
  });
  const latestYear = Math.max(...byYear.keys());
  const priorYear = latestYear - 1;
  const latestSummer = (byYear.get(latestYear) || []).filter((point) => [6, 7, 8].includes(point.month));
  const priorSummer = (byYear.get(priorYear) || []).filter((point) =>
    latestSummer.some((current) => current.month === point.month)
  );
  const commonMonths = latestSummer
    .filter((current) => priorSummer.some((prior) => prior.month === current.month))
    .map((point) => point.month);
  const average = (items) => items.reduce((sum, item) => sum + item.value, 0) / items.length;
  const currentMatched = latestSummer.filter((point) => commonMonths.includes(point.month));
  const priorMatched = priorSummer.filter((point) => commonMonths.includes(point.month));
  const currentAverage = currentMatched.length ? average(currentMatched) : null;
  const priorAverage = priorMatched.length ? average(priorMatched) : null;

  const seasonalYears = Array.from(byYear.entries()).filter(([, items]) => items.length >= 10);
  const monthLifts = new Map();
  seasonalYears.forEach(([, items]) => {
    const yearAverage = average(items);
    items.forEach((point) => {
      if (!monthLifts.has(point.month)) monthLifts.set(point.month, []);
      monthLifts.get(point.month).push((point.value / yearAverage - 1) * 100);
    });
  });
  const seasonal = Array.from(monthLifts.entries()).map(([month, lifts]) => ({
    month,
    lift: lifts.reduce((sum, value) => sum + value, 0) / lifts.length,
  }));
  seasonal.sort((a, b) => b.lift - a.lift);

  return {
    summer: currentAverage != null && priorAverage
      ? {
          year: latestYear,
          priorYear,
          months: commonMonths,
          currentAverage,
          priorAverage,
          changePct: ((currentAverage - priorAverage) / priorAverage) * 100,
          partial: commonMonths.length < 3,
        }
      : null,
    peak: seasonal[0] || null,
    trough: seasonal.length ? seasonal[seasonal.length - 1] : null,
    yearsAnalyzed: seasonalYears.map(([year]) => year),
  };
}

function firstUsableSeries(series, keys) {
  for (const key of keys) {
    const points = series[key];
    if (Array.isArray(points) && points.length >= 2) return points;
  }
  return null;
}

export function buildOverlayModel(series = {}) {
  let definitions = OVERLAY_DEFINITIONS.map((definition) => {
    const points = firstUsableSeries(series, definition.seriesKeys);
    return points ? { ...definition, points } : null;
  }).filter(Boolean);
  if (!definitions.length) return { definitions: [], rows: [], rawByKey: {}, from: null, to: null };

  const from = definitions.map((definition) => definition.points[0].t).sort().at(-1);
  const to = definitions.map((definition) => definition.points.at(-1).t).sort()[0];
  definitions = definitions.map((definition) => ({
    ...definition,
    points: definition.points.filter((point) => point.t >= from && point.t <= to),
  })).filter((definition) => definition.points.length >= 2);

  const named = {};
  const rawByKey = {};
  definitions.forEach((definition) => {
    named[definition.key] = normalizeUnitInterval(definition.points);
    rawByKey[definition.key] = definition;
  });
  return { definitions, rows: mergeSeries(named), rawByKey, from, to };
}
