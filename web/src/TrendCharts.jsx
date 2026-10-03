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
import { mergeSeries, summarizeSeries } from "./normalize.js";
import { buildOverlayModel } from "./chartModels.js";
import { useTheme } from "./ThemeProvider.jsx";

function formatDate(value, options = { month: "short", year: "numeric" }) {
  if (!value) return "—";
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return value;
  return new Intl.DateTimeFormat("en-US", { timeZone: "UTC", ...options }).format(
    new Date(Date.UTC(year, month - 1, day))
  );
}

function formatNumber(value, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(value);
}

function formatValue(value, kind) {
  if (value == null) return "—";
  if (kind === "money") return `$${formatNumber(value)}`;
  if (kind === "rate") return `${formatNumber(value, 2)}%`;
  return formatNumber(value, 2);
}

function formatChange(summary, kind) {
  if (!summary || Math.abs(summary.change) < 0.000001) return "roughly unchanged";
  const direction = summary.change > 0 ? "up" : "down";
  if (kind === "rate") {
    return `${direction} ${formatNumber(Math.abs(summary.change), 2)} percentage points`;
  }
  return summary.changePct == null
    ? `${direction} ${formatValue(Math.abs(summary.change), kind)}`
    : `${direction} ${formatNumber(Math.abs(summary.changePct), 1)}%`;
}

function OverlayTooltip({ active, payload, label, rawByKey }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="overlay-tooltip">
      <strong>{formatDate(label, { month: "short", day: "numeric", year: "numeric" })}</strong>
      {payload.map((entry) => {
        const definition = rawByKey[entry.dataKey];
        const point = definition && definition.points.find((item) => item.t === label);
        return (
          <div className="overlay-tooltip-row" key={entry.dataKey}>
            <span style={{ color: definition?.color }}>{entry.name}</span>
            <span>{formatValue(point ? point.v : null, definition && definition.kind)}</span>
            <small>{formatNumber((Number(entry.value) || 0) * 100, 0)}% of its own range</small>
          </div>
        );
      })}
    </div>
  );
}

function OverlayExplanation({ definitions, from, to }) {
  return (
    <section className="overlay-explanation" aria-labelledby="overlay-explanation-title">
      <h3 id="overlay-explanation-title">How to read this graph</h3>
      <div className="overlay-guide">
        <strong>Compare direction and timing—not dollar amounts.</strong>
        <span>Each line is independently scaled: 0 is that series’ low and 100 is its high during the shared {formatDate(from)}–{formatDate(to)} window.</span>
        <span>Example: home values at 80 means they are 80% of the way from their period low to high. Stocks at 80 means the same relative position for stocks; it does not mean the two values are equal.</span>
      </div>
      <div className="overlay-series-grid">
        {definitions.map((definition) => {
          const summary = summarizeSeries(definition.points);
          if (!summary) return null;
          return (
            <article className="overlay-series-card" key={definition.key}>
              <div className="overlay-series-heading">
                <span className="overlay-series-dot" style={{ background: definition.color }} />
                <strong>{definition.label}</strong>
              </div>
              <p>{definition.description}</p>
              <div className="overlay-series-stat">
                <span>Latest</span>
                <strong>{formatValue(summary.latest.v, definition.kind)}</strong>
              </div>
              <div className="overlay-series-stat">
                <span>Since {formatDate(summary.start.t)}</span>
                <strong>{formatChange(summary, definition.kind)}</strong>
              </div>
              <div className="overlay-series-stat">
                <span>Position in this range</span>
                <strong>{formatNumber(summary.rangePosition, 0)} / 100</strong>
              </div>
              <small className="overlay-series-meta">
                {definition.source} · {definition.cadence} · {summary.count} observations · {formatDate(summary.start.t)}–{formatDate(summary.latest.t)}
              </small>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function ChartFrame({ children }) {
  return <div className="chart-wrap">{children}</div>;
}

export function HousingTrendChart({ series }) {
  const { palette, theme } = useTheme();
  const inventory = series.inventory || [];
  const dom = series.days_on_market || series.median_dom || series.dom || [];
  const listings = series.new_listings || [];
  const rows = mergeSeries({
    inventory,
    dom,
    listings,
  });

  if (!rows.length) {
    return null;
  }

  return (
    <ChartFrame>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid {...palette.grid} vertical={false} />
          <XAxis dataKey="t" tick={palette.axis} minTickGap={28} />
          <YAxis yAxisId="left" tick={palette.axis} width={44} />
          <YAxis yAxisId="right" orientation="right" tick={palette.axis} width={36} />
          <Tooltip contentStyle={palette.tip} />
          <Legend wrapperStyle={{ fontSize: 11, color: theme.tokens.text }} />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="inventory"
            name="Inventory"
            stroke={palette.housing}
            isAnimationActive={false}
            dot={false}
            strokeWidth={1.6}
            connectNulls
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="listings"
            name="New listings"
            stroke={palette.gspc}
            isAnimationActive={false}
            dot={false}
            strokeWidth={1.4}
            connectNulls
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="dom"
            name="DOM"
            stroke={palette.mortgage}
            isAnimationActive={false}
            dot={false}
            strokeWidth={1.4}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function OverlayChart({ series }) {
  const { palette, theme } = useTheme();
  const { definitions, rows, rawByKey, from, to } = buildOverlayModel(series || {}, palette);

  if (!rows.length) {
    return null;
  }

  return (
    <>
      <ChartFrame>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid {...palette.grid} vertical={false} />
            <XAxis dataKey="t" tick={palette.axis} minTickGap={28} />
            <YAxis
              tick={palette.axis}
              ticks={[0, 0.5, 1]}
              domain={[0, 1]}
              width={36}
              tickFormatter={(value) => Math.round(value * 100)}
              label={{ value: "Own range", angle: -90, position: "insideLeft", fill: theme.tokens.muted, fontSize: 11 }}
            />
            <Tooltip content={<OverlayTooltip rawByKey={rawByKey} />} />
            <Legend wrapperStyle={{ fontSize: 11, color: theme.tokens.text }} />
            {definitions.map((definition) => (
              <Line
                key={definition.key}
                type="monotone"
                dataKey={definition.key}
                name={definition.label}
                stroke={definition.color}
                isAnimationActive={false}
                dot={false}
                strokeWidth={definition.key === "housing" ? 2.4 : 1.8}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </ChartFrame>
      <OverlayExplanation definitions={definitions} from={from} to={to} />
    </>
  );
}
