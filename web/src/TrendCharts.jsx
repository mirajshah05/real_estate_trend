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
import { mergeSeries, normalizeUnitInterval } from "./normalize.js";

const AXIS = { stroke: "#8b8ba0", fontSize: 11 };
const GRID = { stroke: "#2a2a40" };
const TIP = {
  background: "#16162a",
  border: "1px solid #2a2a40",
  color: "#e8e8f0",
  fontSize: 12,
};

function ChartFrame({ children }) {
  return <div className="chart-wrap">{children}</div>;
}

export function HousingTrendChart({ series }) {
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
          <CartesianGrid {...GRID} vertical={false} />
          <XAxis dataKey="t" tick={AXIS} minTickGap={28} />
          <YAxis yAxisId="left" tick={AXIS} width={44} />
          <YAxis yAxisId="right" orientation="right" tick={AXIS} width={36} />
          <Tooltip contentStyle={TIP} />
          <Legend wrapperStyle={{ fontSize: 11, color: "#8b8ba0" }} />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="inventory"
            name="Inventory"
            stroke="#4361ee"
            dot={false}
            strokeWidth={1.6}
            connectNulls
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="listings"
            name="New listings"
            stroke="#e8e8f0"
            dot={false}
            strokeWidth={1.4}
            connectNulls
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="dom"
            name="DOM"
            stroke="#c9a227"
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
  const housing =
    series.zhvi ||
    series.typical_value ||
    series.median_list_price ||
    series.home_value ||
    [];
  const gspc = series.gspc || series.GSPC || series.spx || series["^GSPC"] || [];
  const mortgage =
    series.mortgage_30y ||
    series.MORTGAGE30US ||
    series.mortgage ||
    series.rates ||
    [];

  const named = {};
  if (housing.length) named.housing = normalizeUnitInterval(housing);
  if (gspc.length) named.gspc = normalizeUnitInterval(gspc);
  if (mortgage.length) named.mortgage = normalizeUnitInterval(mortgage);
  const rows = mergeSeries(named);

  if (!rows.length) {
    return null;
  }

  return (
    <ChartFrame>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid {...GRID} vertical={false} />
          <XAxis dataKey="t" tick={AXIS} minTickGap={28} />
          <YAxis tick={AXIS} domain={[0, 1]} width={28} />
          <Tooltip contentStyle={TIP} />
          <Legend wrapperStyle={{ fontSize: 11, color: "#8b8ba0" }} />
          {named.housing && (
            <Line
              type="monotone"
              dataKey="housing"
              name="Home value"
              stroke="#4361ee"
              dot={false}
              strokeWidth={1.6}
              connectNulls
            />
          )}
          {named.gspc && (
            <Line
              type="monotone"
              dataKey="gspc"
              name="^GSPC"
              stroke="#e8e8f0"
              dot={false}
              strokeWidth={1.4}
              connectNulls
            />
          )}
          {named.mortgage && (
            <Line
              type="monotone"
              dataKey="mortgage"
              name="Mortgage"
              stroke="#c9a227"
              dot={false}
              strokeWidth={1.4}
              connectNulls
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
