import { formatCompact, formatMoney, formatPct, kpiDelta, kpiValue, pickKpi } from "../normalize.js";

function Cell({ label, value, delta, money, definition }) {
  const shown = money ? formatMoney(value) : formatCompact(value);
  const d = formatPct(delta);
  const cls = delta == null ? "" : delta > 0 ? "up" : delta < 0 ? "down" : "";
  return (
    <div className="kpi">
      <div className="label">
        {label}
        <button className="term-help" type="button" aria-label={`${label}: ${definition}`} data-tip={definition}>i</button>
      </div>
      <div className="value">{shown}</div>
      <div className={`delta ${cls}`}>{delta == null ? "no Δ" : `YoY ${d}`}</div>
    </div>
  );
}

export default function KpiStrip({ kpis }) {
  const inv = pickKpi(kpis, ["inventory"]);
  const neu = pickKpi(kpis, ["new_listings"]);
  const dom = pickKpi(kpis, ["days_on_market", "median_dom", "dom"]);
  const val = pickKpi(kpis, ["typical_value", "zhvi", "median_list_price", "median_sale_price"]);

  return (
    <div className="kpi-strip">
      <Cell label="Inventory" definition="Homes listed for sale in the selected Zillow metro for the displayed week." value={kpiValue(inv)} delta={kpiDelta(inv, "delta_yoy") ?? kpiDelta(inv, "yoy")} />
      <Cell label="New listings" definition="New for-sale listings added during the displayed week across the selected Zillow metro; this is not an address list." value={kpiValue(neu)} delta={kpiDelta(neu, "delta_yoy") ?? kpiDelta(neu, "yoy")} />
      <Cell label="DOM" definition="Days on market: Zillow's mean days from first listing to pending. It does not measure pending-to-close time." value={kpiValue(dom)} delta={kpiDelta(dom, "delta_yoy") ?? kpiDelta(dom, "yoy")} />
      <Cell
        label="Typical value"
        definition="Zillow Home Value Index estimate for a typical home in the selected metro; it is not a median recorded sale price."
        value={kpiValue(val)}
        delta={kpiDelta(val, "delta_yoy") ?? kpiDelta(val, "yoy")}
        money
      />
    </div>
  );
}
