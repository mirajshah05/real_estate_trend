import { useEffect, useMemo } from "react";
import { CircleMarker, GeoJSON, MapContainer, TileLayer, Tooltip, ZoomControl, useMap } from "react-leaflet";
import SearchBox from "./components/SearchBox.jsx";
import { cityMetric } from "./normalize.js";

const US_CENTER = [39.8, -98.5];
const US_ZOOM = 4;
const CARTO_BASEMAP_KEY = (import.meta.env.VITE_CARTO_BASEMAP_KEY || "").trim();
const CARTO_TILE_URL =
  `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png` +
  (CARTO_BASEMAP_KEY ? `?key=${encodeURIComponent(CARTO_BASEMAP_KEY)}` : "");

const METRICS = [
  { id: "price_change_yoy", label: "Home value · past year" },
  { id: "price_change_mom", label: "Home value · past month" },
  { id: "inventory_change", label: "Listings change" },
];

function colorFor(value, maxAbs) {
  if (value == null || !maxAbs) return "#6b6b80";
  const t = Math.max(-1, Math.min(1, value / maxAbs));
  if (t < 0) {
    return t < -0.5 ? "#c44536" : "#8b5a4a";
  }
  if (t > 0.5) return "#4361ee";
  if (t > 0) return "#3d5a80";
  return "#6b6b80";
}

function radiusFor(value, maxAbs) {
  if (value == null || !maxAbs) return 5;
  const t = Math.min(1, Math.abs(value) / maxAbs);
  return 5 + t * 14;
}

function FlyTo({ target, zoomRequest }) {
  const map = useMap();
  useEffect(() => {
    if (!target || target.lat == null || target.lon == null) return;
    const zoom = target.geo_id && /nation|united states/i.test(`${target.geo_id} ${target.name}`)
      ? US_ZOOM
      : target.kind === "address"
        ? 13
        : target.kind === "zip"
          ? 10
          : target.kind === "city"
            ? 10
            : 10;
    map.flyTo([target.lat, target.lon], zoom, { duration: 0.55 });
  }, [target, map]);
  useEffect(() => {
    if (zoomRequest) map.setZoom(Math.max(map.getZoom(), 12));
  }, [zoomRequest, map]);
  return null;
}

function BoundsReporter({ onBounds }) {
  const map = useMap();
  useEffect(() => {
    const emit = () => {
      const b = map.getBounds();
      onBounds({
        west: b.getWest(),
        south: b.getSouth(),
        east: b.getEast(),
        north: b.getNorth(),
        zoom: map.getZoom(),
      });
    };
    map.on("moveend", emit);
    emit();
    return () => {
      map.off("moveend", emit);
    };
  }, [map, onBounds]);
  return null;
}

export default function MapPanel({
  cities,
  zipFeatures = [],
  governmentAreas = [],
  listings,
  sales = [],
  outlierIds,
  metric,
  onMetric,
  selected,
  zoomRequest,
  marketLabel,
  onSelect,
  onBounds,
  staleLayer,
  staleNote,
  focusedListing,
  onFocusListing,
}) {
  const values = useMemo(
    () => cities.map((c) => cityMetric(c, metric)).filter((v) => v != null),
    [cities, metric]
  );
  const maxAbs = useMemo(() => {
    if (!values.length) return 0;
    return Math.max(...values.map((v) => Math.abs(v)));
  }, [values]);
  const selectedMarket = useMemo(
    () => selected && cities.find((city) => city.geo_id === selected.geo_id),
    [cities, selected]
  );
  const selectedValue = selected
    ? cityMetric(selected, metric) ?? cityMetric(selectedMarket || {}, metric)
    : null;

  return (
    <div className="map-pane">
      <MapContainer
        center={US_CENTER}
        zoom={US_ZOOM}
        minZoom={3}
        maxZoom={14}
        zoomControl={false}
        attributionControl={false}
        preferCanvas
      >
        <TileLayer
          url={CARTO_TILE_URL}
          subdomains="abcd"
        />
        <ZoomControl position="bottomleft" />
        <FlyTo target={selected} zoomRequest={zoomRequest} />
        <BoundsReporter onBounds={onBounds} />

        {governmentAreas.map((area) => (
          <GeoJSON
            key={`${area.area_id}-${area.observation_as_of || "unknown"}`}
            data={{
              type: "Feature",
              properties: { name: area.name },
              geometry: area.geometry,
            }}
            style={{
              color: selected && selected.name === area.name ? "#ffffff" : "#49c6b3",
              weight: selected && selected.name === area.name ? 3 : 1.5,
              fillColor: "#49c6b3",
              fillOpacity: 0.1,
            }}
            eventHandlers={{ click: () => onSelect(area) }}
            onEachFeature={(_feature, layer) => {
              const count = area.parcel_count == null
                ? "parcel count unavailable"
                : `${area.parcel_count.toLocaleString("en-US")} parcels`;
              layer.bindTooltip(
                `${area.name}, CA · ${count} · official county boundary · no sale prices`
              );
            }}
          />
        ))}

        {cities.filter((c) => !/nation:|^united states$/i.test(`${c.geo_id} ${c.name}`)).map((c) => {
          const v = cityMetric(c, metric);
          const outlier = c.is_outlier || (c.geo_id && outlierIds.has(c.geo_id));
          const selectedHere = selected && selected.geo_id === c.geo_id;
          return (
            <CircleMarker
              key={c.geo_id || `${c.lat},${c.lon}`}
              center={[c.lat, c.lon]}
              radius={radiusFor(v, maxAbs) + (selectedHere ? 2 : 0)}
              pathOptions={{
                color: outlier ? "#e9c46a" : selectedHere ? "#ffffff" : colorFor(v, maxAbs),
                weight: outlier || selectedHere ? 2 : 1,
                fillColor: colorFor(v, maxAbs),
                fillOpacity: 0.72,
              }}
              eventHandlers={{
                click: () => onSelect(c),
              }}
            >
              <Tooltip className="rk-tip" direction="top" offset={[0, -4]}>
                <div>
                  {c.name}
                  {c.state ? `, ${c.state}` : ""}
                  {v != null ? ` · ${formatTip(v, metric)}` : " · no value"}
                  {outlier ? " · outlier" : ""}
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}

        {zipFeatures.map((z) => (
          <CircleMarker
            key={z.geo_id}
            center={[z.lat, z.lon]}
            radius={4}
            pathOptions={{ color: "#9aa8ff", weight: 1, fillColor: "#4361ee", fillOpacity: 0.45 }}
          >
            <Tooltip className="rk-tip" direction="top" offset={[0, -3]}>
              <div>{z.name}{z.inventory != null ? ` · ${z.inventory.toLocaleString("en-US")} homes` : ""}</div>
            </Tooltip>
          </CircleMarker>
        ))}

        {listings.map((l) => (
          <CircleMarker
            key={l.listing_id}
            center={[l.lat, l.lon]}
            radius={l.outlier_score != null && l.outlier_score >= 3 ? 6 : 4}
            pathOptions={{
              color: focusedListing && focusedListing.listing_id === l.listing_id
                ? "#ffffff"
                : l.outlier_score != null && l.outlier_score >= 3 ? "#e9c46a" : "#e8e8f0",
              weight: focusedListing && focusedListing.listing_id === l.listing_id ? 3 : 1,
              fillColor: "#e8e8f0",
              fillOpacity: 0.85,
            }}
            eventHandlers={{ click: () => onFocusListing && onFocusListing(l) }}
          >
            <Tooltip className="rk-tip" direction="top">
              <div>
                {l.address && <><strong>{l.address}</strong><br /></>}
                {l.price != null ? `$${l.price.toLocaleString("en-US")}` : "Listing"}
                {l.dom != null ? ` · ${l.dom} listing days on market` : ""}
              </div>
            </Tooltip>
          </CircleMarker>
        ))}

        {sales.map((sale) => (
          <CircleMarker
            key={sale.event_id}
            center={[sale.lat, sale.lon]}
            radius={5}
            pathOptions={{ color: "#49c6b3", weight: 1.5, fillColor: "#49c6b3", fillOpacity: 0.8 }}
          >
            <Tooltip className="rk-tip" direction="top">
              <div>
                {sale.address && <><strong>{sale.address}</strong><br /></>}
                {sale.price != null ? `$${sale.price.toLocaleString("en-US")}` : "Sale price unavailable"}
                {sale.sale_date ? ` · recorded sale ${sale.sale_date}` : ""}
              </div>
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>

      {staleLayer && <div className="stale-hatch" aria-hidden="true" />}

      <div className="map-overlay search">
        <SearchBox
          cities={[...governmentAreas, ...cities]}
          selectedId={selected && selected.geo_id}
          onSelect={onSelect}
        />
      </div>

      <div className="map-overlay metrics">
        <div className="seg">
          {METRICS.map((m) => (
            <button
              key={m.id}
              type="button"
              className={metric === m.id ? "active" : ""}
              onClick={() => onMetric(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div className="map-overlay caption">
        <div className="caption-card">
          {selected ? (
            <>
              <strong>
                {selected.name}
                {selected.state && !selected.name.endsWith(`, ${selected.state}`) ? `, ${selected.state}` : ""}
              </strong>
              <span>
                {metricLabel(metric)}
                {selectedValue != null
                  ? ` · ${formatTip(selectedValue, metric)}`
                  : " · no observation"}
              </span>
              {selected.kind === "city" && marketLabel && marketLabel !== selected.name && (
                <span>Boundary: {selected.name} · market statistics: {marketLabel}.</span>
              )}
            </>
          ) : (
            <>
              <strong>US metros</strong>
              <span>
                {cities.length
                  ? `${cities.length} metro circles · zoom in for ZIP inventory`
                  : "Empty layer until /api/map/cities returns points"}
              </span>
            </>
          )}
          <span>Search a city or click a circle, then choose your next step.</span>
          {(listings.length > 0 || sales.length > 0) && (
            <span> {listings.length} active homes · {sales.length} recorded sales in this viewport.</span>
          )}
          {selected && selected.geometry && selected.kind === "city" && (
            <span>
              {" "}Official {selected.county || "county"} boundary
              {selected.parcel_count != null
                ? ` · ${selected.parcel_count.toLocaleString("en-US")} public parcel records`
                : ""}
              {" · market figures are metro aggregates, not parcel sale prices."}
            </span>
          )}
          {staleNote && <span> {staleNote}</span>}
        </div>
      </div>

      <div className="map-overlay legend">
        <div>{metricLabel(metric)}</div>
        <div className="legend-bar">
          <i style={{ background: "#c44536" }} />
          <i style={{ background: "#8b5a4a" }} />
          <i style={{ background: "#6b6b80" }} />
          <i style={{ background: "#3d5a80" }} />
          <i style={{ background: "#4361ee" }} />
        </div>
        <div className="legend-labels">
          <span>decrease</span>
          <span>increase</span>
        </div>
        <div className="legend-labels">
          <span>Larger circle = larger change</span>
        </div>
        <div className="legend-labels"><span>{metric.startsWith("price") ? "Zillow typical-home estimate (ZHVI)" : "Change in available listings"}</span></div>
        {governmentAreas.length > 0 && (
          <div className="legend-labels">
            <span>teal outline = official city boundary</span>
          </div>
        )}
      </div>
    </div>
  );
}

function metricLabel(metric) {
  return METRICS.find((m) => m.id === metric)?.label || metric;
}

function formatTip(v, metric) {
  if (metric === "inventory_change" && Math.abs(v) > 2) {
    return v.toLocaleString("en-US");
  }
  const pct = Math.abs(v) <= 2 ? v * 100 : v;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}
