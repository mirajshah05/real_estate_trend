import { useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatMoney } from "../normalize.js";
import {
  buildRentalChartRows,
  canonicalRentalStatus,
  canonicalRentalType,
  MONTH_NAMES,
  paddedMoneyDomain,
  rentalPointRadius,
  rentalSeasonality,
  selectCityMarketIndex,
} from "../chartModels.js";
import { Quota } from "./PropertyTable.jsx";
import { EmptyState, ErrorState, LoadingState } from "./StatusState.jsx";
import { useTheme } from "../ThemeProvider.jsx";

const CITIES = ["San Jose", "Sunnyvale", "Mountain View", "Palo Alto"];
const TYPES = ["All", "Apartment", "Townhouse", "Single Family"];
const STATUSES = ["All", "New", "Existing"];

export default function RentalsPanel({
  city,
  onCity,
  months,
  onMonths,
  trends,
  trendsState,
  onRetry,
  onImport,
  importState,
  onEstimate,
  estimateState,
}) {
  const [section, setSection] = useState("trends");

  return (
    <div className="rentals-panel">
      <div className="rentals-heading">
        <div>
          <p className="eyebrow">Bay Area rental research</p>
          <h2>Rent intelligence</h2>
          <p className="panel-caption">Compare up to three years, estimate a home, or add verified historical observations.</p>
        </div>
        <div className="rental-scope-controls">
          <label className="field compact-field">
            <span>City</span>
            <select value={city} onChange={(event) => onCity(event.target.value)}>
              {CITIES.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <label className="field compact-field">
            <span>History</span>
            <select value={months} onChange={(event) => onMonths(Number(event.target.value))}>
              <option value={12}>12 months</option>
              <option value={24}>24 months</option>
              <option value={36}>36 months</option>
            </select>
          </label>
        </div>
      </div>
      <div className="subtabs" role="tablist" aria-label="Rental research tools">
        {[
          ["trends", "Rental trends"],
          ["estimate", "Estimate rent"],
          ["import", "Import data"],
        ].map(([id, label]) => (
          <button
            type="button"
            role="tab"
            id={`rental-tab-${id}`}
            aria-controls={`rental-panel-${id}`}
            aria-selected={section === id}
            className={section === id ? "active" : ""}
            key={id}
            onClick={() => setSection(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {section === "trends" && (
        <div role="tabpanel" id="rental-panel-trends" aria-labelledby="rental-tab-trends">
          <RentalTrends city={city} months={months} trends={trends} state={trendsState} onRetry={onRetry} />
        </div>
      )}
      {section === "estimate" && (
        <div role="tabpanel" id="rental-panel-estimate" aria-labelledby="rental-tab-estimate">
          <EstimateForm city={city} onSubmit={onEstimate} state={estimateState} />
        </div>
      )}
      {section === "import" && (
        <div role="tabpanel" id="rental-panel-import" aria-labelledby="rental-tab-import">
          <ImportForm onImport={onImport} state={importState} />
        </div>
      )}
    </div>
  );
}

function RentalTrends({ city, months, trends, state, onRetry }) {
  const { palette } = useTheme();
  const [propertyType, setPropertyType] = useState("All");
  const [listingStatus, setListingStatus] = useState("All");
  const rows = trends && trends.rows ? trends.rows : [];
  const marketIndex = selectCityMarketIndex(trends?.market_indices, city);
  const showingAverage = propertyType === "All" || listingStatus === "All";
  const chartRows = useMemo(() => buildRentalChartRows({
    rows,
    dateFrom: trends?.date_from,
    dateTo: trends?.date_to,
    propertyType,
    listingStatus,
  }), [rows, propertyType, listingStatus, trends?.date_from, trends?.date_to]);
  const hasChartValues = chartRows.some((row) => [1, 2, 3].some((bed) => row[`bed${bed}`] != null));
  const observedChartRows = chartRows.filter((row) => [1, 2, 3].some((bed) => row[`bed${bed}`] != null));
  const bedroomDomain = paddedMoneyDomain(
    observedChartRows.flatMap((row) => [row.bed1, row.bed2, row.bed3])
  );
  const pointRadius = rentalPointRadius(chartRows);

  if (state.loading) return <LoadingState />;
  if (state.error) {
    return (
      <div className="rental-state-card">
        <ErrorState error={state.error} path={state.error.path} />
        <button type="button" onClick={onRetry}>Retry rental trends</button>
      </div>
    );
  }
  if (!rows.length && !marketIndex) return <EmptyState>No rental observations are cached for {city} yet. Import a CSV or JSON dataset to begin.</EmptyState>;

  const latest = [...chartRows].reverse().find((row) => [1, 2, 3].some((bed) => row[`bed${bed}`] != null));
  return (
    <section className="rental-trends" aria-label={`${city} rental trends`}>
      <Quota usage={trends.rentcast_usage} cached={false} />
      {marketIndex && <MarketIndexChart city={city} months={months} index={marketIndex} />}
      {rows.length > 0 && (
          <div className="panel-title-row">
            <div>
              <h3 id="rental-trends-title">{showingAverage ? "Average" : "Median"} asking rent by bedrooms</h3>
              <p className="panel-caption">{city} · monthly observations · {trends.as_of ? `through ${trends.as_of}` : "latest cached data"}</p>
            </div>
            <div className="trend-filters">
              <label className="field compact-field">
                <span>Home type</span>
                <select value={propertyType} onChange={(event) => setPropertyType(event.target.value)}>
                  {TYPES.map((type) => <option key={type}>{type}</option>)}
                </select>
              </label>
              <label className="field compact-field">
                <span>Listing status</span>
                <select value={listingStatus} onChange={(event) => setListingStatus(event.target.value)}>
                  {STATUSES.map((status) => <option key={status}>{status}</option>)}
                </select>
              </label>
            </div>
          </div>
      )}
      {hasChartValues ? (
        <>
          <div className="rent-kpis" aria-label={`Latest ${showingAverage ? "average" : "median"} asking rents`}>
            {[1, 2, 3].map((bed) => (
              <div className="rent-kpi" key={bed}>
                <span>{bed} bedroom</span>
                <strong>{latest[`bed${bed}`] == null ? "—" : formatMoney(latest[`bed${bed}`])}</strong>
                <small>{latest[`count${bed}`] == null ? latest.month : `${latest[`count${bed}`]} observations · ${latest.month}`}</small>
              </div>
            ))}
          </div>
          <div className="rental-chart" role="img" aria-label={`${months}-month rental price history for ${city}`}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartRows} margin={{ top: 12, right: 12, left: 8, bottom: 0 }}>
                <CartesianGrid {...palette.grid} vertical={false} />
                <XAxis dataKey="month" tick={palette.axis} minTickGap={24} />
                <YAxis tick={palette.axis} width={62} domain={bedroomDomain} tickFormatter={(value) => `$${Math.round(value / 100) / 10}k`} />
                <Tooltip formatter={(value) => formatMoney(value)} contentStyle={palette.tip} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {[1, 2, 3].map((bed) => (
                  <Line key={bed} type="monotone" dataKey={`bed${bed}`} name={`${bed} bedroom`} stroke={palette.bedrooms[bed]} isAnimationActive={false} strokeWidth={2} dot={{ r: pointRadius }} connectNulls={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          {observedChartRows.length === 1 && <p className="scope-note"><strong>One observed month.</strong> Points and the table below show the available values, but a property-level trend needs observations from additional months.</p>}
          <MonthlyRentalTable rows={observedChartRows} />
          <p className="fine-print">Values describe cached asking-rent listings, not guaranteed or signed lease rents. “All” uses observation-count-weighted segment averages; an exact home type and status uses the segment median. Missing groups remain blank rather than being estimated.</p>
        </>
      ) : (
        <EmptyState>{rows.length ? "No observations match these filters. Choose another home type or listing status." : `No bedroom or property-type observations are cached for ${city} yet. Import property records for detailed cuts.`}{marketIndex && " The official all-homes index above remains available."}</EmptyState>
      )}
      <RentalReliability trends={trends} marketIndex={marketIndex} />
    </section>
  );
}

function MarketIndexChart({ city, months, index }) {
  const { palette } = useTheme();
  const points = index.points.map((point) => ({ month: point.month, rent: point.value }));
  const latest = points[points.length - 1];
  const domain = paddedMoneyDomain(points.map((point) => point.rent));
  const seasonal = rentalSeasonality(index.points);
  return (
    <section className="market-index-card" aria-labelledby="rental-market-index-title">
      <div className="panel-title-row">
        <div>
          <p className="eyebrow">Official market benchmark</p>
          <h3 id="rental-market-index-title">Zillow observed rent index</h3>
          <p className="panel-caption">{index.city} · all homes · {points.length} of {months} requested months · through {index.as_of || latest.month}</p>
        </div>
        <strong className="market-index-value">{formatMoney(latest.rent)}</strong>
      </div>
      <div className="rental-chart compact-chart" role="img" aria-label={`Official all-homes rent index for ${city}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
            <CartesianGrid {...palette.grid} vertical={false} />
            <XAxis dataKey="month" tick={palette.axis} minTickGap={24} />
            <YAxis tick={palette.axis} width={62} domain={domain} tickFormatter={(value) => `$${Math.round(value / 100) / 10}k`} />
            <Tooltip formatter={(value) => formatMoney(value)} contentStyle={palette.tip} />
            <Line type="monotone" dataKey="rent" name="All homes" stroke={palette.housing} isAnimationActive={false} strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <SeasonalitySummary seasonal={seasonal} />
      <p className="fine-print">ZORI is an aggregate asking-rent index—not a property estimate or a bedroom/type breakdown.</p>
    </section>
  );
}

function SeasonalitySummary({ seasonal }) {
  if (!seasonal) return null;
  const summer = seasonal.summer;
  return (
    <div className="seasonality-grid" aria-label="Seasonal rental comparison">
      <article>
        <span>Summer comparison</span>
        {summer ? (
          <>
            <strong>{formatSignedPercent(summer.changePct)}</strong>
            <small>{summer.year} vs {summer.priorYear}, matching {summer.months.map((month) => MONTH_NAMES[month - 1].slice(0, 3)).join("–")} months{summer.partial ? " (partial summer)" : ""}</small>
          </>
        ) : <strong>Not enough matching summers</strong>}
      </article>
      <article>
        <span>Historically highest month</span>
        {seasonal.peak ? (
          <>
            <strong>{MONTH_NAMES[seasonal.peak.month - 1]}</strong>
            <small>{formatSignedPercent(seasonal.peak.lift)} vs each complete year’s average · {seasonal.yearsAnalyzed.join(", ")}</small>
          </>
        ) : <strong>Need at least one complete year</strong>}
      </article>
    </div>
  );
}

function MonthlyRentalTable({ rows }) {
  if (!rows.length) return null;
  return (
    <div className="rental-table-wrap">
      <h4>Monthly breakdown</h4>
      <table className="table rental-month-table">
        <thead><tr><th>Month</th><th>1 bedroom</th><th>2 bedrooms</th><th>3 bedrooms</th></tr></thead>
        <tbody>{rows.map((row) => (
          <tr key={row.month}>
            <td>{row.month}</td>
            {[1, 2, 3].map((bed) => <td key={bed}>{row[`bed${bed}`] == null ? "—" : formatMoney(row[`bed${bed}`])}</td>)}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function RentalReliability({ trends, marketIndex }) {
  return (
    <div className="rental-reliability">
      <h4>How reliable is this history?</h4>
      <p><strong>City benchmark:</strong> {marketIndex ? `${marketIndex.points.length} official Zillow ZORI monthly index values. Useful for broad direction and cautious seasonal comparison, but still a modeled asking-rent index—not signed leases.` : "No city benchmark is available."}</p>
      <p><strong>Bedroom/type detail:</strong> {trends.observation_count || 0} cached listing events from {trends.first_observed_on || "—"} to {trends.last_observed_on || "—"}. This is a bounded provider/upload sample, so use it as exploratory evidence rather than a complete market census.</p>
    </div>
  );
}

function formatSignedPercent(value) {
  if (!Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function EstimateForm({ city, onSubmit, state }) {
  const [form, setForm] = useState({
    neighborhood: "",
    beds: "2",
    baths: "1",
    property_type: "Apartment",
    sqft: "",
    year_built: "",
    amenities: "",
  });
  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      city,
      neighborhood: form.neighborhood.trim(),
      bedrooms: Number(form.beds),
      bathrooms: Number(form.baths),
      property_type: form.property_type.toLowerCase().replace(/ /g, "_"),
      sqft: form.sqft ? Number(form.sqft) : null,
      year_built: form.year_built ? Number(form.year_built) : null,
      amenities: form.amenities.split(",").map((item) => item.trim()).filter(Boolean),
    });
  };
  const result = state.data;
  const estimate = result && (result.estimate_monthly_rent ?? result.estimated_rent ?? result.monthly_rent ?? result.estimate ?? result.prediction);
  const low = result && (result.low ?? result.lower_bound ?? result.range?.low);
  const high = result && (result.high ?? result.upper_bound ?? result.range?.high);

  return (
    <section className="tool-section" aria-labelledby="estimate-title">
      <h3 id="estimate-title">Neighborhood rent estimate</h3>
      <p className="panel-caption">Describe the property. The model uses only comparable rental records available to the API.</p>
      <form className="rental-form" onSubmit={submit}>
        <label className="field field-wide"><span>Neighborhood</span><input value={form.neighborhood} onChange={set("neighborhood")} placeholder="e.g. Willow Glen" required /></label>
        <label className="field"><span>Bedrooms</span><select value={form.beds} onChange={set("beds")}>{[1,2,3].map((n) => <option key={n}>{n}</option>)}</select></label>
        <label className="field"><span>Bathrooms</span><input type="number" min="1" max="10" step="0.5" value={form.baths} onChange={set("baths")} required /></label>
        <label className="field"><span>Property type</span><select value={form.property_type} onChange={set("property_type")}>{TYPES.slice(1).map((type) => <option key={type}>{type}</option>)}</select></label>
        <label className="field"><span>Square feet</span><input type="number" min="100" value={form.sqft} onChange={set("sqft")} placeholder="Optional" /></label>
        <label className="field"><span>Year built</span><input type="number" min="1800" max={new Date().getFullYear() + 2} value={form.year_built} onChange={set("year_built")} placeholder="Optional" /></label>
        <label className="field field-wide"><span>Amenities</span><input value={form.amenities} onChange={set("amenities")} placeholder="parking, in-unit laundry, air conditioning" /></label>
        <div className="form-actions field-wide">
          <button className="primary-button" type="submit" disabled={state.loading}>{state.loading ? "Estimating…" : "Estimate monthly rent"}</button>
          <span>For research only; not an appraisal.</span>
        </div>
      </form>
      {state.error && <div className="inline-alert" role="alert">{state.error.message}</div>}
      {result && estimate != null && (
        <div className="estimate-result" aria-live="polite">
          <span>Estimated monthly rent</span>
          <strong>{formatMoney(Number(estimate))}</strong>
          {low != null && high != null && <span>Likely range {formatMoney(Number(low))}–{formatMoney(Number(high))}</span>}
          {(result.sample_size ?? result.comparable_count) != null && <small>Based on {result.sample_size ?? result.comparable_count} comparable observations</small>}
          {result.confidence && <small>Confidence: {typeof result.confidence === "string" ? result.confidence : `${result.confidence.label}${result.confidence.score != null ? ` (${Math.round(result.confidence.score * 100)}%)` : ""}`}</small>}
          {(result.methodology || result.method) && <small>{String(result.methodology || result.method).replaceAll("_", " ")}</small>}
          {Array.isArray(result.adjustments) && result.adjustments.length > 0 && (
            <details><summary>Estimate adjustments</summary><ul>{result.adjustments.map((item, index) => <li key={`${index}-${String(item.factor || item)}`}>{typeof item === "string" ? item : `${item.description || item.label || item.factor || "Adjustment"}${item.impact_dollars != null ? ` (${item.impact_dollars >= 0 ? "+" : ""}${formatMoney(item.impact_dollars)})` : ""}`}</li>)}</ul></details>
          )}
          {Array.isArray(result.comparables) && result.comparables.length > 0 && (
            <details><summary>{result.comparables.length} closest comparables</summary><ul className="comparable-list">{result.comparables.slice(0, 5).map((item) => <li key={item.observation_id}><span>{item.neighborhood || item.city} · {item.bedrooms} bd · {canonicalRentalType(item.property_type)}</span><strong>{formatMoney(item.monthly_rent)}</strong></li>)}</ul></details>
          )}
          {result.disclaimer && <small>{result.disclaimer}</small>}
        </div>
      )}
      {result && estimate == null && (
        <div className="inline-alert" role="status">No defensible estimate is available yet. Add more matching rental observations and try again.</div>
      )}
    </section>
  );
}

function ImportForm({ onImport, state }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [localError, setLocalError] = useState("");
  const choose = (candidate) => {
    if (!candidate) return;
    const ext = candidate.name.split(".").pop().toLowerCase();
    if (!["csv", "json"].includes(ext)) {
      setFile(null);
      setLocalError("Choose a .csv or .json file.");
      return;
    }
    setFile(candidate);
    setLocalError("");
  };
  const submit = async () => {
    if (!file) return;
    try {
      const content = await file.text();
      await onImport({ filename: file.name, format: file.name.toLowerCase().endsWith(".json") ? "json" : "csv", content });
    } catch (error) {
      setLocalError(error.message || "Could not read that file.");
    }
  };

  return (
    <section className="tool-section" aria-labelledby="import-title">
      <h3 id="import-title">Update historical rental data</h3>
      <p className="panel-caption">Upload a CSV or JSON export. The server validates, deduplicates, and caches accepted observations.</p>
      <div
        className="drop-zone"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => { event.preventDefault(); choose(event.dataTransfer.files[0]); }}
      >
        <input ref={inputRef} type="file" accept=".csv,.json,text/csv,application/json" onChange={(event) => choose(event.target.files[0])} />
        <span className="upload-mark" aria-hidden="true">↑</span>
        <strong>{file ? file.name : "Drop rental data here"}</strong>
        <span>{file ? `${Math.max(1, Math.round(file.size / 1024)).toLocaleString("en-US")} KB ready` : "or choose a CSV / JSON file"}</span>
        <button type="button" onClick={() => inputRef.current?.click()}>Choose file</button>
      </div>
      <div className="schema-note">
        <strong>Required columns</strong>
        <code>observed_on, city, monthly_rent, bedrooms, property_type, listing_status</code>
        <span>Accepted cities: San Jose, Sunnyvale, Mountain View, Palo Alto.</span>
      </div>
      {(localError || state.error) && (
        <div className="inline-alert" role="alert">
          <div>{localError || state.error.message}</div>
          {Array.isArray(state.error?.details) && state.error.details.length > 0 && (
            <ul className="validation-errors">
              {state.error.details.slice(0, 8).map((detail, index) => (
                <li key={`${detail.row || "item"}-${index}`}>
                  {detail.row ? `Row ${detail.row}: ` : ""}
                  {Array.isArray(detail.errors)
                    ? detail.errors.map((item) => item.msg || String(item)).join("; ")
                    : detail.observation_id || "Invalid observation"}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <button className="primary-button" type="button" disabled={!file || state.loading} onClick={submit}>{state.loading ? "Importing…" : "Validate and import"}</button>
      {state.data && (
        <div className="import-result" aria-live="polite">
          <strong>Import complete</strong>
          <span>{state.data.imported ?? state.data.accepted ?? ((state.data.inserted || 0) + (state.data.updated || 0))} accepted · {state.data.skipped ?? state.data.duplicates ?? state.data.rejected ?? 0} rejected</span>
          {(state.data.inserted != null || state.data.updated != null) && <span>{state.data.inserted || 0} inserted · {state.data.updated || 0} updated</span>}
          {state.data.message && <span>{state.data.message}</span>}
        </div>
      )}
    </section>
  );
}
