/**
 * RealtyKit API client.
 * Canonical paths stay wired even when a route 404s.
 * Tokens: localhost-only bearer from localStorage (realtykit_token).
 * Off localhost, session tokens must not live in localStorage.
 */

const FIXTURE_MAP = {
  "/api/freshness": "/fixtures/freshness.json",
  "/api/map/cities": "/fixtures/map-cities.json",
  "/api/kpis": "/fixtures/kpis.json",
  "/api/trends": "/fixtures/trends.json",
  "/api/correlation": "/fixtures/correlation.json",
  "/api/outliers": "/fixtures/outliers.json",
  "/api/stocks/dips": "/fixtures/stocks-dips.json",
  "/api/map/listings": "/fixtures/map-listings.json",
  "/api/health": "/fixtures/health.json",
};

export class ApiError extends Error {
  constructor(message, { status = 0, code = "network", path = "", offline = false, details = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.path = path;
    this.offline = offline;
    this.details = details;
  }
}

function isLoopbackHost() {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return host === "localhost" || host === "127.0.0.1";
}

function authHeaders() {
  const headers = { Accept: "application/json" };
  if (isLoopbackHost()) {
    const token = window.localStorage.getItem("realtykit_token");
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }
  return headers;
}

function fixturePathFor(apiPath) {
  const bare = apiPath.split("?")[0];
  return FIXTURE_MAP[bare] || null;
}

async function readJson(res, path) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError("Invalid JSON from API", {
      status: res.status,
      code: "invalid_json",
      path,
    });
  }
}

export async function getJson(path, { signal } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method: "GET",
      headers: authHeaders(),
      cache: "no-store",
      signal,
    });
  } catch (err) {
    if (err && err.name === "AbortError") throw err;
    throw new ApiError("API unreachable", {
      status: 0,
      code: "offline",
      path,
      offline: true,
    });
  }

  if (!res.ok) {
    const raw = await res.text();
    let body = null;
    if (raw) {
      try {
        body = JSON.parse(raw);
      } catch {
        body = null;
      }
    }
    const message =
      (body && body.error && body.error.message) ||
      `Request failed (${res.status})`;
    const offline =
      res.status === 502 ||
      res.status === 503 ||
      res.status === 504 ||
      (res.status === 500 && /proxy|econnrefused|ECONNREFUSED/i.test(raw || ""));
    throw new ApiError(message, {
      status: res.status,
      code: (body && body.error && body.error.code) || "http_error",
      path,
      offline,
      details: body && body.error && body.error.details,
    });
  }

  return readJson(res, path);
}

export async function postJson(path, body) {
  let res;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: {
        ...authHeaders(),
        "Content-Type": "application/json",
      },
      cache: "no-store",
      body: JSON.stringify(body || {}),
    });
  } catch {
    throw new ApiError("API unreachable", {
      status: 0,
      code: "offline",
      path,
      offline: true,
    });
  }

  if (!res.ok) {
    const payload = await readJson(res, path).catch(() => null);
    throw new ApiError(
      (payload && payload.error && payload.error.message) || `Request failed (${res.status})`,
      {
        status: res.status,
        code: (payload && payload.error && payload.error.code) || "http_error",
        path,
        offline: res.status === 502 || res.status === 503 || res.status === 504,
        details: payload && payload.error && payload.error.details,
      }
    );
  }

  return readJson(res, path);
}

async function tryFixture(apiPath) {
  const fixture = fixturePathFor(apiPath);
  if (!fixture) return null;
  try {
    const res = await fetch(fixture, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Prefer the live API. On transport / 5xx failure, try a Vite public fixture
 * only if that file already exists. Never invent market numbers.
 */
export async function getApiOrFixture(path, { signal } = {}) {
  try {
    const data = await getJson(path, { signal });
    return { data, source: "api", error: null };
  } catch (err) {
    if (err && err.name === "AbortError") throw err;
    if (err && (err.offline || err.status === 0)) {
      const fixture = await tryFixture(path);
      if (fixture) {
        return { data: fixture, source: "fixture", error: err };
      }
      return { data: null, source: "none", error: err };
    }
    // Reachable API, missing or invalid route — keep the UI wired.
    return { data: null, source: "api", error: err };
  }
}

export function withGeo(path, geoId) {
  const url = new URL(path, "http://local.invalid");
  if (geoId) url.searchParams.set("geo_id", geoId);
  return `${url.pathname}${url.search}`;
}

export const paths = {
  health: "/api/health",
  freshness: "/api/freshness",
  mapCities: "/api/map/cities",
  governmentAreas: "/api/map/government-areas",
  mapListings: "/api/map/listings",
  mapSales: (bbox, lookbackDays = 365) =>
    `/api/map/sales?bbox=${encodeURIComponent(bbox)}&lookback_days=${lookbackDays}&limit=500`,
  mapZips: (bbox) => `/api/map/zips?bbox=${encodeURIComponent(bbox)}`,
  search: (query) => `/api/search?q=${encodeURIComponent(query)}`,
  research: (geoId, months = 36) => {
    const url = new URL("/api/research", "http://local.invalid");
    if (geoId) url.searchParams.set("geo_id", geoId);
    url.searchParams.set("months", String(months));
    return `${url.pathname}${url.search}`;
  },
  kpis: (geoId) => withGeo("/api/kpis", geoId),
  trends: (geoId, metrics) => {
    const url = new URL("/api/trends", "http://local.invalid");
    if (geoId) url.searchParams.set("geo_id", geoId);
    if (metrics) url.searchParams.set("metrics", metrics);
    return `${url.pathname}${url.search}`;
  },
  correlation: (geoId) => withGeo("/api/correlation", geoId),
  outliers: (geoId) => {
    const url = new URL("/api/outliers", "http://local.invalid");
    if (geoId) url.searchParams.set("geo_id", geoId);
    url.searchParams.set("kind", "all");
    return `${url.pathname}${url.search}`;
  },
  stockDips: "/api/stocks/dips",
  rentalTrends: (city, months = 12) => {
    const url = new URL("/api/rentals/trends", "http://local.invalid");
    if (city) url.searchParams.set("city", city);
    url.searchParams.set("months", String(months));
    return `${url.pathname}${url.search}`;
  },
  rentalImport: "/api/rentals/import",
  rentalEstimate: "/api/rentals/estimate",
  refresh: "/api/ingest/refresh",
};

export async function probeApi() {
  const health = await getApiOrFixture(paths.health);
  if (health.data) {
    return { online: health.source === "api", health: health.data, error: health.error };
  }
  const freshness = await getApiOrFixture(paths.freshness);
  if (freshness.source === "api") {
    return { online: true, health: null, error: null };
  }
  if (freshness.source === "fixture") {
    return { online: false, health: null, error: freshness.error, fixture: true };
  }
  return { online: false, health: null, error: health.error || freshness.error };
}
