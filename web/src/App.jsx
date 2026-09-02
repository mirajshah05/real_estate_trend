import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getApiOrFixture, paths, postJson } from "./api.js";
import Dock from "./components/Dock.jsx";
import FreshnessBanner from "./components/FreshnessBanner.jsx";
import MapPanel from "./MapPanel.jsx";
import {
  nationalGeoId,
  normalizeCities,
  normalizeCorrelation,
  normalizeDips,
  normalizeGovernmentAreas,
  normalizeListings,
  normalizeSales,
  normalizeOutliers,
  normalizeTrends,
  kpiValue,
  pickKpi,
} from "./normalize.js";

const TREND_METRICS =
  "inventory,days_on_market,new_listings,zhvi,median_list_price,gspc,mortgage_30y";

function routeGeoId(pathname) {
  const m = pathname.match(/^\/city\/(.+)$/);
  if (!m) return null;
  try {
    return decodeURIComponent(m[1]);
  } catch {
    return m[1];
  }
}

function Dashboard() {
  const location = useLocation();
  const navigate = useNavigate();
  const routeGeo = routeGeoId(location.pathname);

  const [apiOnline, setApiOnline] = useState(null);
  const [freshness, setFreshness] = useState(null);
  const [cities, setCities] = useState([]);
  const [zipFeatures, setZipFeatures] = useState([]);
  const [governmentAreas, setGovernmentAreas] = useState([]);
  const [citiesError, setCitiesError] = useState(null);
  const [listings, setListings] = useState([]);
  const [listingsMeta, setListingsMeta] = useState({ loading: false, error: null, usage: null, cached: false });
  const [sales, setSales] = useState([]);
  const [salesState, setSalesState] = useState({ loading: false, error: null, usage: null, cached: false });
  const [selected, setSelected] = useState(null);
  const [metric, setMetric] = useState("price_change_yoy");
  const [tab, setTab] = useState(location.pathname === "/sources" ? "sources" : "trends");
  const [refreshing, setRefreshing] = useState(false);
  const [bounds, setBounds] = useState(null);

  const [kpis, setKpis] = useState(null);
  const [kpisState, setKpisState] = useState({ loading: true, error: null, data: null });
  const [trends, setTrends] = useState(null);
  const [trendsState, setTrendsState] = useState({ loading: true, error: null, data: null });
  const [corr, setCorr] = useState(null);
  const [corrState, setCorrState] = useState({ loading: true, error: null, data: null });
  const [outliers, setOutliers] = useState([]);
  const [outliersState, setOutliersState] = useState({ loading: true, error: null, data: null });
  const [dips, setDips] = useState(null);
  const [dipsState, setDipsState] = useState({ loading: true, error: null, data: null });
  const [research, setResearch] = useState(null);
  const [researchState, setResearchState] = useState({ loading: true, error: null, data: null });

  const outlierIds = useMemo(() => {
    const ids = new Set();
    for (const row of outliers) {
      if (row.subject_id) ids.add(row.subject_id);
    }
    for (const c of cities) {
      if (c.is_outlier && c.geo_id) ids.add(c.geo_id);
    }
    return ids;
  }, [outliers, cities]);

  const staleLayer = useMemo(() => {
    const block = freshness && (freshness.freshness || freshness);
    return block && block.overall === "stale";
  }, [freshness]);

  const selectCity = useCallback(
    (city) => {
      if (!city) return;
      setSelected(city);
      if (city.geo_id) {
        navigate(`/city/${encodeURIComponent(city.geo_id)}`, { replace: true });
      }
    },
    [navigate]
  );

  const loadShell = useCallback(async () => {
    const [freshRes, mapRes, governmentRes] = await Promise.all([
      getApiOrFixture(paths.freshness),
      getApiOrFixture(paths.mapCities),
      getApiOrFixture(paths.governmentAreas),
    ]);

    const fromApi = [freshRes, mapRes, governmentRes].some((r) => r.source === "api");
    setApiOnline(fromApi);
    if (freshRes.data) setFreshness(freshRes.data);

    if (mapRes.data) {
      const list = normalizeCities(mapRes.data);
      setCities(list);
      setGovernmentAreas(
        governmentRes.data ? normalizeGovernmentAreas(governmentRes.data) : []
      );
      setCitiesError(null);
      return list;
    }
    setCities([]);
    setGovernmentAreas(
      governmentRes.data ? normalizeGovernmentAreas(governmentRes.data) : []
    );
    setCitiesError(mapRes.error);
    return [];
  }, []);

  const loadGeo = useCallback(async (geoId) => {
    const id = geoId || "nation:US";
    setKpisState({ loading: true, error: null, data: null });
    setTrendsState({ loading: true, error: null, data: null });
    setCorrState({ loading: true, error: null, data: null });
    setOutliersState({ loading: true, error: null, data: null });
    setResearchState({ loading: true, error: null, data: null });

    const [k, t, c, o, r] = await Promise.all([
      getApiOrFixture(paths.kpis(id)),
      getApiOrFixture(paths.trends(id, TREND_METRICS)),
      getApiOrFixture(paths.correlation(id)),
      getApiOrFixture(paths.outliers(id)),
      getApiOrFixture(paths.research(id)),
    ]);

    if ([k, t, c, o, r].some((item) => item.source === "api")) setApiOnline(true);
    applySlice(k, setKpis, setKpisState, (d) => d);
    applySlice(t, setTrends, setTrendsState, normalizeTrends);
    applySlice(c, setCorr, setCorrState, normalizeCorrelation);
    applySlice(o, setOutliers, setOutliersState, normalizeOutliers);
    applySlice(r, setResearch, setResearchState, (d) => d);
  }, []);

  const loadDips = useCallback(async () => {
    setDipsState({ loading: true, error: null, data: null });
    const res = await getApiOrFixture(paths.stockDips);
    if (res.source === "api") setApiOnline(true);
    applySlice(res, setDips, setDipsState, normalizeDips);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const list = await loadShell();
      if (cancelled) return;
      await loadDips();
      if (cancelled) return;

      const match =
        (routeGeo && list.find((c) => c.geo_id === routeGeo)) ||
        list.find((c) => /united states/i.test(c.name)) ||
        null;
      const geo = match || {
        geo_id: routeGeo || nationalGeoId(list),
        name: match ? match.name : "United States",
        lat: match && match.lat != null ? match.lat : 39.8,
        lon: match && match.lon != null ? match.lon : -98.5,
      };
      setSelected(geo);
      await loadGeo(geo.geo_id);
    })();
    return () => {
      cancelled = true;
    };
    // Shell loads once; geo clicks call loadGeo directly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (location.pathname === "/sources") setTab("sources");
  }, [location.pathname]);

  useEffect(() => {
    if (!selected || !routeGeo || selected.geo_id === routeGeo) return;
    const match = cities.find((c) => c.geo_id === routeGeo);
    if (match) {
      setSelected(match);
      loadGeo(match.geo_id);
    }
  }, [routeGeo, cities, selected, loadGeo]);

  useEffect(() => {
    setSales([]);
    setSalesState({ loading: false, error: null, usage: null, cached: false });
    if (!bounds || bounds.zoom < 10) {
      setListings([]);
      setListingsMeta({ loading: false, error: null, usage: null, cached: false });
      return;
    }
    let cancelled = false;
    const bbox = `${bounds.west},${bounds.south},${bounds.east},${bounds.north}`;
    let timer = null;
    if (tab === "homes") {
      const path = `${paths.mapListings}?bbox=${encodeURIComponent(bbox)}`;
      setListingsMeta((current) => ({ ...current, loading: true, error: null }));
      timer = window.setTimeout(() => {
        getApiOrFixture(path).then((res) => {
          if (cancelled) return;
          setListings(res.data ? normalizeListings(res.data) : []);
          setListingsMeta({
            loading: false,
            error: res.error,
            usage: res.data && res.data.usage,
            cached: Boolean(res.data && res.data.cached),
            note: (res.data && res.data.note) || "",
          });
        });
      }, 500);
    } else {
      setListings([]);
    }
    if (bounds.zoom >= 7) {
      getApiOrFixture(paths.mapZips(bbox)).then((res) => {
        if (cancelled) return;
        setZipFeatures(res.data ? normalizeCities(res.data) : []);
      });
    } else {
      setZipFeatures([]);
    }
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [bounds, tab]);

  const loadSales = useCallback(async () => {
    if (!bounds || bounds.zoom < 10) return;
    const bbox = `${bounds.west},${bounds.south},${bounds.east},${bounds.north}`;
    setSalesState((current) => ({ ...current, loading: true, error: null }));
    const res = await getApiOrFixture(paths.mapSales(bbox));
    setSales(res.data ? normalizeSales(res.data) : []);
    setSalesState({
      loading: false,
      error: res.error,
      usage: res.data && res.data.usage,
      cached: Boolean(res.data && res.data.cached),
      note: (res.data && res.data.note) || "",
    });
  }, [bounds]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await postJson(paths.refresh, { force: false });
    } catch {
      /* keep canonical GETs even if refresh 404s */
    }
    const list = await loadShell();
    await loadDips();
    const geo = (selected && selected.geo_id) || nationalGeoId(list);
    await loadGeo(geo);
    setRefreshing(false);
  };

  const onSelectCity = (city) => {
    if (!city) return;
    const marketId = city.market_geo_id || city.geo_id;
    const target = marketId && marketId !== city.geo_id ? { ...city, geo_id: marketId } : city;
    selectCity(target);
    if (marketId) loadGeo(marketId);
  };

  const onPickOutlier = (subjectId) => {
    const city = cities.find((c) => c.geo_id === subjectId);
    if (city) onSelectCity(city);
  };

  const onTab = (next) => {
    setTab(next);
    if (next === "sources") navigate("/sources", { replace: true });
  };

  const mapNote =
    staleLayer
      ? "Active layer is stale. This is historical, not current."
      : citiesError && !cities.length
        ? "Map points unavailable from /api/map/cities."
        : "";
  const marketLabel = useMemo(() => {
    if (!selected) return "United States";
    const market = cities.find((city) => city.geo_id === selected.geo_id);
    return market ? market.name : selected.name;
  }, [cities, selected]);
  const metroNewListings = kpiValue(pickKpi(kpis, ["new_listings"]));

  return (
    <div className="shell">
      <FreshnessBanner
        freshness={freshness}
        apiOnline={apiOnline}
        refreshing={refreshing}
        onRefresh={onRefresh}
        onOpenSources={() => onTab("sources")}
      />
      <div className="main">
        <MapPanel
          cities={cities}
          zipFeatures={zipFeatures}
          governmentAreas={governmentAreas}
          listings={listings}
          sales={sales}
          outlierIds={outlierIds}
          metric={metric}
          onMetric={setMetric}
          selected={selected}
          marketLabel={marketLabel}
          onSelect={onSelectCity}
          onBounds={setBounds}
          staleLayer={staleLayer}
          staleNote={mapNote}
        />
        <Dock
          apiOnline={apiOnline}
          tab={tab}
          onTab={onTab}
          selected={selected}
          marketLabel={marketLabel}
          kpis={kpis}
          kpisState={kpisState}
          trends={trends}
          trendsState={trendsState}
          corr={corr}
          corrState={corrState}
          outliers={outliers}
          outliersState={outliersState}
          dips={dips}
          dipsState={dipsState}
          research={research}
          researchState={researchState}
          freshness={freshness}
          onPickOutlier={onPickOutlier}
          listings={listings}
          listingsMeta={listingsMeta}
          metroNewListings={metroNewListings}
          sales={sales}
          salesState={salesState}
          onLoadSales={loadSales}
          canLoadSales={Boolean(bounds && bounds.zoom >= 10)}
        />
      </div>
      <footer className="footer">
        <span>
          Map tiles ©{" "}
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">
            OpenStreetMap
          </a>{" "}
          ©{" "}
          <a href="https://carto.com/attributions" target="_blank" rel="noopener noreferrer">
            CARTO
          </a>
          . Data: Zillow Research · Redfin Data Center · FRED · Yahoo Finance · Census · county GIS.
        </span>
        <span>Local dashboard · observation as-of is the freshness clock</span>
      </footer>
    </div>
  );
}

function applySlice(res, setData, setState, normalize) {
  if (res.data) {
    const n = normalize(res.data);
    setData(n);
    setState({ loading: false, error: null, data: n });
    return;
  }
  setData(res.data);
  setState({ loading: false, error: res.error, data: null });
}

export default function App() {
  return <Dashboard />;
}
