import { HousingTrendChart, OverlayChart } from "../TrendCharts.jsx";
import CorrelationPanel from "./CorrelationPanel.jsx";
import KpiStrip from "./KpiStrip.jsx";
import OutlierTable from "./OutlierTable.jsx";
import ResearchPanel from "./ResearchPanel.jsx";
import SourcesPanel from "./SourcesPanel.jsx";
import StockDips from "./StockDips.jsx";
import { EmptyState, ErrorState, LoadingState, OfflinePanel } from "./StatusState.jsx";

const TABS = [
  { id: "trends", label: "Trends" },
  { id: "overlay", label: "Overlay" },
  { id: "corr", label: "Correlation" },
  { id: "outliers", label: "Outliers" },
  { id: "dips", label: "Dips" },
  { id: "research", label: "Research" },
  { id: "sources", label: "Sources" },
];

export default function Dock({
  apiOnline,
  tab,
  onTab,
  selected,
  kpis,
  kpisState,
  trends,
  trendsState,
  corr,
  corrState,
  outliers,
  outliersState,
  dips,
  dipsState,
  research,
  researchState,
  freshness,
  onPickOutlier,
}) {
  const asOf = selected && (kpis && kpis.as_of);
  const geoLabel = selected ? selected.name : "United States";

  return (
    <aside className="dock">
      <KpiStrip kpis={kpis} />
      <nav className="dock-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? "active" : ""}
            onClick={() => onTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className="dock-body">
        {apiOnline === false && <OfflinePanel />}

        {apiOnline !== false && tab === "trends" && (
          <>
            <h2>Inventory · DOM · new listings</h2>
            <p className="panel-caption">
              {geoLabel}
              {asOf ? ` · as of ${asOf}` : ""}
              {" · Zillow weekly when present"}
            </p>
            <PanelGate state={trendsState} empty="No housing series from /api/trends.">
              <HousingTrendChart series={(trends && trends.series) || {}} />
              {trends && trends.series && !hasHousing(trends.series) && (
                <EmptyState>No housing series from /api/trends.</EmptyState>
              )}
            </PanelGate>
          </>
        )}

        {apiOnline !== false && tab === "overlay" && (
          <>
            <h2>Home value vs ^GSPC vs mortgage</h2>
            <p className="panel-caption">Normalized 0–1 per series. Missing series are omitted.</p>
            <PanelGate state={trendsState} empty="Overlay needs series from /api/trends.">
              <OverlayChart series={(trends && trends.series) || {}} />
              {trends && !hasOverlay(trends.series) && (
                <EmptyState>
                  Overlay needs housing and macro series from /api/trends. Mortgage
                  stays omitted while FRED is unavailable.
                </EmptyState>
              )}
            </PanelGate>
          </>
        )}

        {apiOnline !== false && tab === "corr" && (
          <>
            <h2>Correlation</h2>
            <PanelGate state={corrState} empty="No correlation payload.">
              <CorrelationPanel corr={corr} />
            </PanelGate>
          </>
        )}

        {apiOnline !== false && tab === "outliers" && (
          <>
            <h2>Market outliers</h2>
            <PanelGate state={outliersState} empty={null}>
              <OutlierTable
                rows={outliers || []}
                selectedId={selected && selected.geo_id}
                onSelect={onPickOutlier}
              />
            </PanelGate>
          </>
        )}

        {apiOnline !== false && tab === "dips" && (
          <>
            <h2>Stock dips</h2>
            <PanelGate state={dipsState} empty="No dip payload from /api/stocks/dips.">
              <StockDips dips={dips} />
            </PanelGate>
          </>
        )}

        {apiOnline !== false && tab === "research" && (
          <>
            <h2>Area research</h2>
            <ResearchPanel research={research} state={researchState} geoLabel={geoLabel} />
          </>
        )}

        {tab === "sources" && (
          <>
            <h2>Sources</h2>
            <p className="panel-caption">
              Zillow Research, Redfin (stale), Compass unavailable, Yahoo, FRED.
            </p>
            <SourcesPanel freshness={freshness} />
          </>
        )}
      </div>
    </aside>
  );
}

function hasHousing(series) {
  return Boolean(
    (series.inventory && series.inventory.length) ||
      (series.days_on_market && series.days_on_market.length) ||
      (series.new_listings && series.new_listings.length)
  );
}

function hasOverlay(series) {
  if (!series) return false;
  return Boolean(
    (series.zhvi && series.zhvi.length) ||
      (series.gspc && series.gspc.length) ||
      (series.mortgage_30y && series.mortgage_30y.length) ||
      (series.median_list_price && series.median_list_price.length)
  );
}

function PanelGate({ state, empty, children }) {
  if (state.loading) return <LoadingState />;
  if (state.error) return <ErrorState error={state.error} path={state.error.path} />;
  if (!state.data && empty) return <EmptyState>{empty}</EmptyState>;
  return children;
}
