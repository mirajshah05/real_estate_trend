import { formatPct } from "../normalize.js";
import { EmptyState } from "./StatusState.jsx";

export default function StockDips({ dips }) {
  if (!dips || !dips.dips) {
    return <EmptyState>No dip payload from /api/stocks/dips.</EmptyState>;
  }

  const last = dips.last;
  const lookback = dips.lookback_days ? `${dips.lookback_days}-day event lookback` : "recent events";
  const threshold = dips.threshold_window_weeks
    ? `${dips.threshold_window_weeks}-week rolling thresholds`
    : "rolling thresholds";
  const history =
    dips.history_start && dips.history_end
      ? `Loaded history: ${dips.history_start}–${dips.history_end}.`
      : "No stock history is currently loaded.";
  return (
    <>
      {last && (
        <p className="panel-caption">
          {dips.symbol} last {last.t || "—"}
          {last.close != null ? ` · ${last.close.toLocaleString("en-US")}` : ""}
          {last.drawdown_52w != null ? ` · 52w ${formatPct(last.drawdown_52w)}` : ""}
        </p>
      )}
      <p className="scope-note">
        <strong>Scope:</strong> {lookback} · {threshold}. {history} This is not an all-history
        crisis list; 2008 is outside the loaded range.
      </p>
      {dips.dips.length === 0 ? (
        <EmptyState>No dip events in this recent lookback window.</EmptyState>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Kind</th>
              <th>Close</th>
              <th>From peak</th>
            </tr>
          </thead>
          <tbody>
            {dips.dips.map((d, i) => (
              <tr key={`${d.t}-${i}`}>
                <td>{d.t || "—"}</td>
                <td>{d.kind}</td>
                <td>{d.close == null ? "—" : d.close.toLocaleString("en-US")}</td>
                <td>{formatPct(d.from_peak)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
