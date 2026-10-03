export default function SalesEvidence({ sales, state, areaLabel }) {
  const evidence = state.evidence || {};
  const withPrice = sales.filter(row => row.price != null).length;
  const retrieved = [...new Set(sales.map(row => row.fetched_at).filter(Boolean))].sort();
  const cityCounts = new Map();
  for (const row of sales) {
    const place = [row.city || "City unknown", row.state].filter(Boolean).join(", ");
    cityCounts.set(place, (cityCounts.get(place) || 0) + 1);
  }
  const cities = [...cityCounts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const cityName = areaLabel?.split(",")[0].trim();
  const cityMatches = cityName ? sales.filter(row => row.city?.trim().toLowerCase() === cityName.toLowerCase()).length : 0;
  return <section className="sales-evidence" aria-label="Sale data source and coverage">
    <div className="evidence-heading"><strong>{sales.length} provider-reported sale events</strong><span>RentCast property records</span></div>
    <p role="status">Visible map area around {areaLabel || "your selection"}. Nearby cities may be included; this is not a count inside the city boundary.</p>
    <dl className="evidence-grid">
      <div><dt>Search window</dt><dd>{evidence.date_from && evidence.date_to ? `${evidence.date_from} – ${evidence.date_to}` : "Past 12 months"}</dd></div>
      <div><dt>Sale-price coverage</dt><dd>{withPrice} with prices · {sales.length - withPrice} not supplied</dd></div>
      <div><dt>Retrieved from provider</dt><dd>{retrieved.length ? retrieved[retrieved.length - 1] : "No records returned"}{state.cached ? " · cached" : ""}</dd></div>
      <div><dt>Completeness</dt><dd>One sample of up to {evidence.record_limit || 500} property records. Not exhaustive.</dd></div>
      {cityName && cityName !== "United States" && <div><dt>Selected city label</dt><dd>{cityMatches} records labeled “{cityName}” by the provider, within this sample.</dd></div>}
    </dl>
    {cities.length > 0 && <p className="evidence-cities">Cities in these results: {cities.slice(0, 5).map(([city, count]) => `${city} (${count})`).join(" · ")}{cities.length > 5 ? ` · ${cities.length - 5} other cities` : ""}</p>}
    <details><summary>Where these records come from</summary>
      <p>Each row is a sale-history event or the last-sale fields supplied by RentCast. Assessment values and asking prices are excluded. Records are checked for a valid sale date, the search window and a location inside the map bounds. The date is a provider sale date, not a separately verified deed-recording date.</p>
      <p>County recording delays and missing prices affect coverage. We have not independently verified these records with the county recorder.</p>
      <a href="https://developers.rentcast.io/reference/property-records" target="_blank" rel="noopener noreferrer">RentCast property-record documentation ↗</a>
      {evidence.query_bounds?.length === 4 && <p className="fine-print">Search bounds (west, south, east, north): {evidence.query_bounds.map(value => Number(value).toFixed(4)).join(", ")}</p>}
    </details>
  </section>;
}
