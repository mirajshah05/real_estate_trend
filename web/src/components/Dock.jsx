import { HousingTrendChart, OverlayChart } from "../TrendCharts.jsx";
import CorrelationPanel from "./CorrelationPanel.jsx";
import KpiStrip from "./KpiStrip.jsx";
import OutlierTable from "./OutlierTable.jsx";
import ResearchPanel from "./ResearchPanel.jsx";
import RentalsPanel from "./RentalsPanel.jsx";
import SourcesPanel from "./SourcesPanel.jsx";
import StockDips from "./StockDips.jsx";
import TaskLanding from "./TaskLanding.jsx";
import SimilarHomesPanel from "./SimilarHomesPanel.jsx";
import { ListingsPanel, SalesPanel } from "./PropertyTable.jsx";
import { EmptyState, ErrorState, LoadingState, OfflinePanel } from "./StatusState.jsx";

const TABS = [
  { id: "overview", label: "Start here", scope: "NEXT STEPS" },
  { id: "similar", label: "Similar homes", scope: "YOUR SEARCH" },
  { id: "rentals", label: "Rent intelligence", scope: "BAY AREA" },
  { id: "trends", label: "Trends", scope: "AREA" },
  { id: "sales", label: "Sales", scope: "VIEWPORT" },
  { id: "homes", label: "Map listings", scope: "VIEWPORT" },
  { id: "overlay", label: "Overlay", scope: "AREA × US" },
  { id: "corr", label: "Correlation", scope: "AREA × US" },
  { id: "outliers", label: "Outliers", scope: "AREA / US" },
  { id: "dips", label: "Dips", scope: "US" },
  { id: "research", label: "Research", scope: "AREA + US" },
  { id: "sources", label: "Sources", scope: "GLOBAL" },
];

export default function Dock({
  apiOnline,
  tab,
  onTab,
  selected,
  marketLabel,
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
  listings,
  listingsMeta,
  metroNewListings,
  sales,
  salesState,
  onLoadSales,
  canLoadSales,
  onZoom,
  searchCities,
  propertyFocus,
  focusedListing,
  onFocusListing,
  researchFocus,
  onResearchFocus,
  rentalCity,
  onRentalCity,
  rentalMonths,
  onRentalMonths,
  rentalTrends,
  rentalTrendsState,
  onRetryRentalTrends,
  onImportRentals,
  rentalImportState,
  onEstimateRent,
  rentalEstimateState,
}) {
  const asOf = selected && (kpis && kpis.as_of);
  const geoLabel = selected ? selected.name : "United States";
  const selectedTab = TABS.find((item) => item.id === tab);
  const boundaryLabel = selected && selected.kind === "city" ? `${geoLabel} boundary` : geoLabel;
  const areaContext = selected && selected.kind === "city" && marketLabel !== geoLabel
    ? `${boundaryLabel} · market figures use ${marketLabel}`
    : marketLabel || geoLabel;

  return (
    <aside className="dock">
      {!["overview", "similar", "rentals", "sources"].includes(tab) && <KpiStrip kpis={kpis} />}
      <div className="workspace-controls" aria-label="Workspace layout">
        <span>{tab === "similar" ? "Home search" : tab === "rentals" ? "Rental research" : geoLabel}</span>
        <div className="seg">
          <button type="button" aria-pressed={!researchFocus} className={!researchFocus ? "active" : ""} onClick={() => onResearchFocus(false)}>Map + data</button>
          <button type="button" aria-pressed={researchFocus} className={researchFocus ? "active" : ""} onClick={() => onResearchFocus(true)}>Full screen</button>
        </div>
      </div>
      <nav className="dock-tabs">
        {TABS.slice(0, 5).map((t) => (
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
      <details className="more-tools" open={TABS.slice(5).some(item => item.id === tab) || undefined}>
        <summary>More research tools &amp; data sources</summary>
        <nav className="dock-tabs">{TABS.slice(5).map(t => <button key={t.id} type="button" className={tab === t.id ? "active" : ""} onClick={() => onTab(t.id)}>{t.label}</button>)}</nav>
      </details>
      <div className="dock-body">
        {!["overview", "similar"].includes(tab) && <div className="scope-bar">
          <strong>{selectedTab ? selectedTab.scope : "AREA"}</strong>
          <span>{scopeDescription(tab, areaContext)}</span>
        </div>}
        {apiOnline === false && <OfflinePanel />}
        {tab === "overview" && <TaskLanding selected={selected} onTab={onTab} />}
        {tab === "similar" && <SimilarHomesPanel selected={selected} cities={searchCities} />}

        {apiOnline !== false && tab === "trends" && (
          <>
            <h2>Inventory · DOM · new listings</h2>
            <p className="panel-caption">
              {areaContext}
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

        {apiOnline !== false && tab === "homes" && (
          <ListingsPanel
            listings={listings}
            meta={listingsMeta}
            metroNewListings={metroNewListings}
            gallery={propertyFocus}
            focusedListing={focusedListing}
            onFocus={onFocusListing}
          />
        )}

        {apiOnline !== false && tab === "sales" && (
          <SalesPanel sales={sales} state={salesState} onLoad={onLoadSales} canLoad={canLoadSales} onZoom={onZoom} areaLabel={geoLabel} />
        )}

        {apiOnline !== false && tab === "overlay" && (
          <>
            <h2>Home value vs S&amp;P 500 vs mortgage rate</h2>
            <p className="panel-caption">{areaContext} housing compared with national stocks and mortgage rates. Each line is normalized independently.</p>
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
            <p className="panel-caption">{areaContext} housing versus national stocks and mortgage rates. Correlation is not causation.</p>
            <PanelGate state={corrState} empty="No correlation payload.">
              <CorrelationPanel corr={corr} />
            </PanelGate>
          </>
        )}

        {apiOnline !== false && tab === "outliers" && (
          <>
            <h2>Market outliers</h2>
            <p className="panel-caption">Address-level outliers when viewport homes are cached; otherwise a US metro cohort.</p>
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
            <p className="panel-caption">National S&amp;P 500 history; changing the selected city does not refresh this tab.</p>
            <PanelGate state={dipsState} empty="No dip payload from /api/stocks/dips.">
              <StockDips dips={dips} />
            </PanelGate>
          </>
        )}

        {apiOnline !== false && tab === "research" && (
          <>
            <h2>Area research</h2>
            <ResearchPanel research={research} state={researchState} geoLabel={areaContext} />
          </>
        )}

        {tab === "rentals" && (
          <RentalsPanel
            city={rentalCity}
            onCity={onRentalCity}
            months={rentalMonths}
            onMonths={onRentalMonths}
            trends={rentalTrends}
            trendsState={rentalTrendsState}
            onRetry={onRetryRentalTrends}
            onImport={onImportRentals}
            importState={rentalImportState}
            onEstimate={onEstimateRent}
            estimateState={rentalEstimateState}
          />
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

function scopeDescription(tab, areaContext) {
  if (tab === "homes" || tab === "sales") return "Refreshes from the visible map area, not the metro KPI selection.";
  if (tab === "overlay" || tab === "corr") return `${areaContext} housing combined with national comparison series.`;
  if (tab === "dips") return "National stock data; unchanged when a city is selected.";
  if (tab === "sources") return "Application-wide provider status and freshness.";
  if (tab === "outliers") return "Uses local homes when available; otherwise compares US metros.";
  if (tab === "research") return `${areaContext}, with national context.`;
  if (tab === "rentals") return "Up to 36 months of rental research for four core Bay Area cities.";
  return `${areaContext}; refreshes when the selected market changes.`;
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
