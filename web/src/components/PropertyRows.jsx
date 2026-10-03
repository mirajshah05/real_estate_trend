import { formatMoney } from "../normalize.js";

const ORIGINS = { sale_history: "Sale event in property history", last_sale_fields: "Last-sale date and price fields" };

export function PropertyRows({ rows, dateKey, empty, gallery = false, focusedListing, onFocus }) {
  if (!rows || !rows.length) return <div className="empty compact">{empty}</div>;
  return <div className={`property-list${gallery ? " property-gallery" : ""}`}>
    {rows.map(row => <article key={row.listing_id || row.event_id}
      className={`property-row${focusedListing?.listing_id === row.listing_id && row.listing_id ? " selected" : ""}`}
      role={gallery && onFocus ? "button" : undefined}
      aria-pressed={gallery && onFocus ? focusedListing?.listing_id === row.listing_id : undefined}
      tabIndex={gallery && onFocus ? 0 : undefined}
      onClick={gallery && onFocus ? () => onFocus(row) : undefined}
      onKeyDown={gallery && onFocus ? event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onFocus(row); } } : undefined}>
      {gallery && <div className="property-photo">{row.photos?.[0]
        ? <img src={row.photos[0]} alt={`Exterior of ${row.address || "property"}`} loading="lazy" />
        : <span aria-label="Property photo unavailable">Photo unavailable</span>}</div>}
      <div><strong>{row.address || "Address unavailable"}</strong><span>{[row.city, row.state, row.zip_code].filter(Boolean).join(", ")}</span></div>
      <div className="property-numbers"><strong>{row.price == null ? "Price unavailable" : formatMoney(row.price)}</strong>
        <span>{dateKey === "sale_date" ? "Sale date: " : "Observed: "}{row[dateKey] || "unavailable"}</span></div>
      <div className="property-facts">
        {row.property_type && <span>{row.property_type}</span>}
        {row.beds != null && <span>{row.beds} bd</span>}
        {row.baths != null && <span>{row.baths} ba</span>}
        {row.sqft != null && <span>{Math.round(row.sqft).toLocaleString("en-US")} ft²</span>}
        {row.dom != null && <span title="Listing days on market">{Math.round(row.dom)} DOM</span>}
      </div>
      {row.match_reasons && <p className="match-reasons">{row.match_reasons.join(" · ")}{row.intent === "rent" ? " · asking rent per month" : " · asking sale price"}</p>}
      {row.event_id && <div className="sale-record-source">
        <span>RentCast property record · {row.price == null ? "sale price not supplied" : "reported sale price"}</span>
        <details className="record-details"><summary>Source &amp; record details</summary>
          <dl><dt>Provider property ID</dt><dd>{row.property_id || "Unavailable"}</dd>
            <dt>Sale evidence</dt><dd>{ORIGINS[row.record_origin] || "Provider sale fields; origin not stored in this older record"}</dd>
            <dt>Retrieved</dt><dd>{row.fetched_at || "Unavailable"}</dd>
            <dt>Confirmation</dt><dd>Provider-supplied record; not independently checked against a county deed. Confirm important details with the county recorder.</dd></dl>
        </details>
      </div>}
    </article>)}
  </div>;
}
