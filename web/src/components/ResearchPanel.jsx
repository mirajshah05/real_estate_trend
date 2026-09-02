import { formatCompact, formatMoney, formatPct, asNumber } from "../normalize.js";
import { EmptyState, ErrorState, LoadingState } from "./StatusState.jsx";

const MONEY = new Set(["zhvi", "median_sale_price"]);
const PERCENT = new Set(["price_change_yoy", "price_change_mom"]);
const RATE = new Set(["mortgage_30y"]);

function valueFor(metric, value) {
  if (value == null) return "—";
  if (MONEY.has(metric)) return formatMoney(value);
  if (PERCENT.has(metric)) return formatPct(value);
  if (RATE.has(metric)) return `${value.toFixed(2)}%`;
  return formatCompact(value);
}

export default function ResearchPanel({ research, state, geoLabel }) {
  if (state.loading) return <LoadingState />;
  if (state.error) return <ErrorState error={state.error} path={state.error.path} />;
  if (!research) return <EmptyState>No cached research for this area yet.</EmptyState>;

  const metrics = (research.metrics || []).filter((m) => m.value != null);
  return (
    <div className="research-panel">
      <p className="panel-caption">
        {geoLabel}{research.as_of ? ` · latest observation ${research.as_of}` : ""}
      </p>
      <div className="research-metrics">
        {metrics.map((m) => (
          <div className="research-metric" key={m.metric}>
            <div className="label">{m.label}</div>
            <div className="value">{valueFor(m.metric, asNumber(m.value))}</div>
            <div className="meta">{m.provider || "unknown"} · {m.period_end || "no date"}</div>
          </div>
        ))}
      </div>
      <h3>What the cache says</h3>
      <ul className="research-insights">
        {(research.insights || []).map((item) => <li key={item}>{item}</li>)}
      </ul>
      {research.national_context && research.national_context.length > 0 && (
        <>
          <h3>United States context</h3>
          <div className="research-context">
            {research.national_context.slice(0, 4).map((m) => (
              <span key={m.metric}>{m.label}: {valueFor(m.metric, asNumber(m.value))}</span>
            ))}
          </div>
        </>
      )}
      <h3>Sources used</h3>
      <div className="research-sources">
        {(research.sources || []).map((source) => source.url ? (
          <a key={source.source_id} href={source.url} target="_blank" rel="noopener noreferrer">
            {source.provider} · {source.dataset || source.source_id} · {source.status}
          </a>
        ) : (
          <span key={source.source_id}>
            {source.provider} · {source.dataset || source.source_id} · {source.status}
          </span>
        ))}
      </div>
      <div className="research-disclaimer">
        {(research.disclaimers || []).map((item) => <div key={item}>{item}</div>)}
      </div>
    </div>
  );
}
