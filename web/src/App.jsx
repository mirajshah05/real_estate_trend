import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getApiOrFixture, getJson, paths, postJson } from "./api.js";
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
  normalizeRentalTrends,
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

function marketSelection(city) {
  if (!city) return null;
  const marketId = city.market_geo_id || city.geo_id;
  return marketId && marketId !== city.geo_id ? { ...city, area_geo_id: city.geo_id, geo_id: marketId } : city;
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
  const [tab, setTab] = useState(location.pathname === "/sources" ? "sources" : "overview");
  const [refreshing, setRefreshing] = useState(false);
  const [bounds, setBounds] = useState(null);
  const [researchFocus, setResearchFocus] = useState(false);
  const [focusedListing, setFocusedListing] = useState(null);
  const [rentalCity, setRentalCity] = useState("San Jose");
  const [rentalMonths, setRentalMonths] = useState(36);
  const [rentalTrends, setRentalTrends] = useState(null);
  const [rentalTrendsState, setRentalTrendsState] = useState({ loading: false, error: null, data: null });
  const [rentalImportState, setRentalImportState] = useState({ loading: false, error: null, data: null });
  const [rentalEstimateState, setRentalEstimateState] = useState({ loading: false, error: null, data: null });
  const rentalRequestRef = useRef(0);
  const salesRequestRef = useRef(0);
  const geoRequestRef = useRef(0);
  const pendingSelectionRef = useRef(null);
  const [zoomRequest, setZoomRequest] = useState(0);

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
    for (const row of outliers || []) {
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
      pendingSelectionRef.current = city;
      setSelected(city);
      if (city.geo_id) {
        navigate(`/city/${encodeURIComponent(city.area_geo_id || city.geo_id)}`, { replace: true });
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
      const areas = governmentRes.data ? normalizeGovernmentAreas(governmentRes.data) : [];
      setCities(list);
      setGovernmentAreas(areas);
      setCitiesError(null);
      return [...areas, ...list];
    }
    setCities([]);
    setGovernmentAreas(
      governmentRes.data ? normalizeGovernmentAreas(governmentRes.data) : []
    );
    setCitiesError(mapRes.error);
    return [];
  }, []);

  const loadGeo = useCallback(async (geoId) => {
    const requestId = ++geoRequestRef.current;
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
    if (requestId !== geoRequestRef.current) return;

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
      const geo = marketSelection(match) || {
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
    const pending = pendingSelectionRef.current;
    if (pending) {
      if ((pending.area_geo_id || pending.geo_id) === routeGeo) {
        pendingSelectionRef.current = null;
        setSelected(pending);
      }
      return;
    }
    if (!selected || !routeGeo || (selected.area_geo_id || selected.geo_id) === routeGeo) return;
    const match = marketSelection([...governmentAreas, ...cities].find((c) => c.geo_id === routeGeo));
    if (match) {
      setSelected(match);
      loadGeo(match.geo_id);
    }
  }, [routeGeo, cities, governmentAreas, selected, loadGeo]);

  useEffect(() => {
    salesRequestRef.current += 1;
    setSales([]);
    setSalesState({ loading: false, error: null, usage: null, cached: false, loaded: false });
  }, [bounds]);

  useEffect(() => {
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
    const requestId = ++salesRequestRef.current;
    const bbox = `${bounds.west},${bounds.south},${bounds.east},${bounds.north}`;
    setSales([]);
    setSalesState((current) => ({ ...current, loading: true, error: null }));
    let res;
    try {
      res = { data: await getJson(paths.mapSales(bbox)), error: null };
    } catch (error) {
      res = { data: null, error };
    }
    if (requestId !== salesRequestRef.current) return;
    setSales(res.data ? normalizeSales(res.data) : []);
    setSalesState({
      loading: false,
      loaded: Boolean(res.data),
      evidence: res.data ? { query_bounds: res.data.query_bounds, record_limit: res.data.record_limit, date_from: res.data.date_from, date_to: res.data.date_to } : null,
      error: res.error,
      usage: res.data && res.data.usage,
      cached: Boolean(res.data && res.data.cached),
      note: (res.data && res.data.note) || "",
    });
  }, [bounds]);

  const loadRentalTrends = useCallback(async (city, months) => {
    const requestId = ++rentalRequestRef.current;
    setRentalTrendsState({ loading: true, error: null, data: null });
    const res = await getApiOrFixture(paths.rentalTrends(city, months));
    if (requestId !== rentalRequestRef.current) return;
    if (res.data) {
      const data = normalizeRentalTrends(res.data);
      setRentalTrends(data);
      setRentalTrendsState({ loading: false, error: null, data });
    } else {
      setRentalTrends(null);
      setRentalTrendsState({ loading: false, error: res.error, data: null });
    }
  }, []);

  useEffect(() => {
    if (tab !== "rentals") return;
    loadRentalTrends(rentalCity, rentalMonths);
  }, [tab, rentalCity, rentalMonths, loadRentalTrends]);

  const importRentals = useCallback(async (payload) => {
    setRentalImportState({ loading: true, error: null, data: null });
    try {
      const data = await postJson(paths.rentalImport, payload);
      setRentalImportState({ loading: false, error: null, data: data || {} });
      await loadRentalTrends(rentalCity, rentalMonths);
      return data;
    } catch (error) {
      setRentalImportState({ loading: false, error, data: null });
      throw error;
    }
  }, [loadRentalTrends, rentalCity, rentalMonths]);

  const estimateRent = useCallback(async (payload) => {
    setRentalEstimateState({ loading: true, error: null, data: null });
    try {
      const data = await postJson(paths.rentalEstimate, payload);
      setRentalEstimateState({ loading: false, error: null, data: data || {} });
    } catch (error) {
      setRentalEstimateState({ loading: false, error, data: null });
    }
  }, []);

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
    setTab("overview");
    setResearchFocus(false);
    if (["San Jose", "Sunnyvale", "Mountain View", "Palo Alto"].includes(city.name)) setRentalCity(city.name);
    const marketId = city.market_geo_id || city.geo_id;
    const target = marketSelection(city);
    selectCity(target);
    if (marketId) loadGeo(marketId);
  };

  const onPickOutlier = (subjectId) => {
    const city = cities.find((c) => c.geo_id === subjectId);
    if (city) onSelectCity(city);
  };

  const onTab = (next) => {
    setTab(next);
    if (next === "rentals" && ["San Jose", "Sunnyvale", "Mountain View", "Palo Alto"].includes(selected?.name)) setRentalCity(selected.name);
    setResearchFocus(next === "rentals" || next === "similar");
    if (next === "sources") navigate("/sources", { replace: true });
    else if (location.pathname === "/sources") navigate(selected?.geo_id ? `/city/${encodeURIComponent(selected.area_geo_id || selected.geo_id)}` : "/", { replace: true });
  };

  const onFocusListing = (listing) => {
    setFocusedListing(listing);
    setTab("homes");
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
  const propertyFocus = !researchFocus && tab === "homes" && Boolean(bounds && bounds.zoom >= 12);

  return (
    <div className="shell">
      <FreshnessBanner
        freshness={freshness}
        apiOnline={apiOnline}
        refreshing={refreshing}
        onRefresh={onRefresh}
        onOpenSources={() => onTab("sources")}
      />
      <nav className="taskbar" aria-label="Main tasks">
        <button type="button" className={tab === "overview" ? "active" : ""} onClick={() => onTab("overview")}>Explore markets</button>
        <button type="button" className={tab === "similar" ? "active" : ""} onClick={() => onTab("similar")}>Find similar homes</button>
        <button type="button" className={tab === "rentals" ? "active" : ""} onClick={() => onTab("rentals")}>Rent intelligence</button>
      </nav>
      <div className={`main${researchFocus ? " research-focus" : ""}${propertyFocus ? " property-focus" : ""}`}>
        {!researchFocus && <MapPanel
          cities={cities}
          zipFeatures={zipFeatures}
          governmentAreas={governmentAreas}
          listings={listings}
          sales={sales}
          outlierIds={outlierIds}
          metric={metric}
          onMetric={setMetric}
          selected={selected}
          zoomRequest={zoomRequest}
          marketLabel={marketLabel}
          onSelect={onSelectCity}
          onBounds={setBounds}
          staleLayer={staleLayer}
          staleNote={mapNote}
          focusedListing={focusedListing}
          onFocusListing={onFocusListing}
        />}
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
          onZoom={() => { setResearchFocus(false); setZoomRequest(value => value + 1); }}
          searchCities={[...governmentAreas, ...cities]}
          propertyFocus={propertyFocus}
          focusedListing={focusedListing}
          onFocusListing={setFocusedListing}
          researchFocus={researchFocus}
          onResearchFocus={setResearchFocus}
          rentalCity={rentalCity}
          onRentalCity={setRentalCity}
          rentalMonths={rentalMonths}
          onRentalMonths={setRentalMonths}
          rentalTrends={rentalTrends}
          rentalTrendsState={rentalTrendsState}
          onRetryRentalTrends={() => loadRentalTrends(rentalCity, rentalMonths)}
          onImportRentals={importRentals}
          rentalImportState={rentalImportState}
          onEstimateRent={estimateRent}
          rentalEstimateState={rentalEstimateState}
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
          . Data: Zillow Research · Redfin Data Center · RentCast · FRED · Yahoo Finance · Census · county GIS.
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
