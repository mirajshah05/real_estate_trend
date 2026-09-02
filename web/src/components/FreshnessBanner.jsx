import { honestySummary, sourcesPanelRows } from "../normalize.js";

const STATUS_LABEL = {
  live: "live",
  fresh: "fresh",
  aging: "aging",
  stale: "stale",
  by_design_monthly: "monthly",
  unavailable: "unavailable",
};

function chipDetail(row) {
  const bits = [];
  if (row.as_of) bits.push(`obs ${row.as_of}`);
  if (row.file_date) bits.push(`file ${row.file_date}`);
  bits.push(STATUS_LABEL[row.status] || row.status);
  return bits.join(" · ");
}

export default function FreshnessBanner({
  freshness,
  apiOnline,
  refreshing,
  onRefresh,
  onOpenSources,
}) {
  const rows = sourcesPanelRows(freshness);
  const honesty = honestySummary(freshness, apiOnline);
  const stalePresent = rows.some((r) => r.status === "stale" || r.status === "aging");

  return (
    <header className="banner">
      <div className="banner-top">
        <div className="banner-brand">RealtyKit</div>
        <div className="banner-honesty">{honesty}</div>
        <div className="banner-actions">
          {apiOnline === false && <span className="chip warn">API offline</span>}
          <button type="button" onClick={onRefresh} disabled={refreshing || apiOnline === false}>
            {refreshing ? "Refreshing" : "Refresh"}
          </button>
        </div>
      </div>
      <div className="banner-chips">
        {rows.map((row) => (
          <button
            key={row.id}
            type="button"
            className={`chip status-${row.status}`}
            onClick={onOpenSources}
          >
            <span className="dot" />
            {row.provider}
            {" — "}
            {chipDetail(row)}
          </button>
        ))}
        {stalePresent && (
          <span className="chip warn">
            Observation age is the SLA clock — a new file is not a live week
          </span>
        )}
      </div>
    </header>
  );
}
