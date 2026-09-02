import { formatSigned } from "../normalize.js";
import { EmptyState } from "./StatusState.jsx";

export default function CorrelationPanel({ corr }) {
  if (!corr || (!corr.pairs.length && !corr.insufficient)) {
    return <EmptyState>No correlation pairs from /api/correlation.</EmptyState>;
  }

  if (corr.insufficient) {
    return (
      <>
        <EmptyState>insufficient_history — series too short to score.</EmptyState>
        <p className="disclaimer">{corr.disclaimer}</p>
      </>
    );
  }

  return (
    <>
      <p className="panel-caption">
        {corr.aligned_cadence || "weekly"}
        {corr.n != null ? ` · n=${corr.n}` : ""}
      </p>
      <div className="corr-grid">
        <div className="head">Pair</div>
        <div className="head">Pearson</div>
        <div className="head">Spearman</div>
        {corr.pairs.map((p, i) => (
          <div key={`${p.a}-${p.b}-${i}`} style={{ display: "contents" }}>
            <div>
              {p.a} × {p.b}
              {p.lag_weeks ? ` (lag ${p.lag_weeks}w)` : ""}
            </div>
            <div>{formatSigned(p.pearson)}</div>
            <div>{formatSigned(p.spearman)}</div>
          </div>
        ))}
      </div>
      {corr.best_lags.length > 0 && (
        <p className="panel-caption">
          Best lag: {corr.best_lags[0].a} leads {corr.best_lags[0].b} by{" "}
          {corr.best_lags[0].lag_weeks}w
          {corr.best_lags[0].note ? ` — ${corr.best_lags[0].note}` : ""}
        </p>
      )}
      <p className="disclaimer">{corr.disclaimer}</p>
    </>
  );
}
