import { formatMoney } from "../normalize.js";

export function Quota({ usage, cached }) {
  if (!usage) return null;
  return (
    <div className={`quota ${usage.alert ? "warn" : ""}`}>
      <span>RentCast: {usage.attempted_requests}/{usage.limit} attempted requests this month</span>
      <span>{cached ? "served from local cache" : `${usage.remaining} remaining`}</span>
      {usage.alert && <strong>{usage.alert}</strong>}
      <small>Local counter started with this app; check the provider dashboard for account-wide usage.</small>
    </div>
  );
}

export function ListingsPanel({ listings, meta, metroNewListings, gallery, focusedListing, onFocus }) {
  return (
    <>
      <h2>Address-level homes for sale</h2>
      <p className="panel-caption">
        Visible map area · RentCast active listings. {metroNewListings != null
          ? `${Math.round(metroNewListings).toLocaleString("en-US")} “new listings” above is a weekly metro aggregate and cannot be expanded into the same number of addresses.`
          : "The Zillow metro aggregate is separate from these address-level records."}
      </p>
      {meta && meta.error && <div className="inline-alert">{meta.error.message}</div>}
      <Quota usage={meta && meta.usage} cached={meta && meta.cached} />
      {gallery && listings.length > 0 && <p className="scope-note"><strong>Gallery view</strong> Close zoom gives property photos and details more room. Select a card or map pin to focus a home.</p>}
      <PropertyRows rows={listings} dateKey="as_of" empty="No active address-level homes returned for this viewport. Zoom to a target city after activating RentCast." gallery={gallery} focusedListing={focusedListing} onFocus={onFocus} />
    </>
  );
}

export function SalesPanel({ sales, state, onLoad, canLoad }) {
  return (
    <>
      <div className="panel-title-row">
        <div>
          <h2>Recorded sale history</h2>
          <p className="panel-caption">Visible map area · last 12 months · on demand to conserve the hard 40-attempt monthly budget.</p>
        </div>
        <button type="button" onClick={onLoad} disabled={!canLoad || state.loading}>
          {state.loading ? "Loading…" : "Load sales"}
        </button>
      </div>
      {!canLoad && <div className="inline-alert">Zoom to level 10 or closer before loading sales.</div>}
      {state.error && <div className="inline-alert">{state.error.message}</div>}
      <Quota usage={state.usage} cached={state.cached} />
      <p className="fine-print">Sale events come from property records, not assessments. County recording delays may be weeks or months; owner fields are discarded before storage.</p>
      <PropertyRows rows={sales} dateKey="sale_date" empty="No sale events loaded yet." />
    </>
  );
}

function PropertyRows({ rows, dateKey, empty, gallery = false, focusedListing, onFocus }) {
  if (!rows || !rows.length) return <div className="empty compact">{empty}</div>;
  return (
    <div className={`property-list${gallery ? " property-gallery" : ""}`}>
      {rows.map((row) => (
        <article
          key={row.listing_id || row.event_id}
          className={`property-row${focusedListing && focusedListing.listing_id === row.listing_id ? " selected" : ""}`}
          role={gallery && onFocus ? "button" : undefined}
          aria-pressed={gallery && onFocus ? Boolean(focusedListing && focusedListing.listing_id === row.listing_id) : undefined}
          tabIndex={gallery && onFocus ? 0 : undefined}
          onClick={gallery && onFocus ? () => onFocus(row) : undefined}
          onKeyDown={gallery && onFocus ? (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onFocus(row); } } : undefined}
        >
          {gallery && (
            <div className="property-photo">
              {row.photos && row.photos[0]
                ? <img src={row.photos[0]} alt={`Exterior of ${row.address || "property"}`} loading="lazy" />
                : <span aria-label="Property photo unavailable">Photo unavailable</span>}
            </div>
          )}
          <div>
            <strong>{row.address || "Address unavailable"}</strong>
            <span>{[row.city, row.state, row.zip_code].filter(Boolean).join(", ")}</span>
          </div>
          <div className="property-numbers">
            <strong>{formatMoney(row.price)}</strong>
            <span>{row[dateKey] || "date unavailable"}</span>
          </div>
          <div className="property-facts">
            {row.beds != null && <span>{row.beds} bd</span>}
            {row.baths != null && <span>{row.baths} ba</span>}
            {row.sqft != null && <span>{Math.round(row.sqft).toLocaleString("en-US")} ft²</span>}
            {row.dom != null && <span title="Listing days on market">{Math.round(row.dom)} DOM</span>}
          </div>
        </article>
      ))}
    </div>
  );
}
