import { PropertyRows } from "./PropertyRows.jsx";
import PaginatedProperties from "./PaginatedProperties.jsx";
import SalesEvidence from "./SalesEvidence.jsx";
export { PropertyRows } from "./PropertyRows.jsx";

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

export function SalesPanel({ sales, state, onLoad, canLoad, onZoom, areaLabel }) {
  return (
    <>
      <div className="panel-title-row">
        <div>
          <h2>Recorded sale history</h2>
          <p className="panel-caption">Visible map area · last 12 months · on demand to conserve the hard 40-attempt monthly budget.</p>
        </div>
        <button type="button" onClick={onLoad} disabled={!canLoad || state.loading}>
          {state.loading ? "Searching…" : "Search recent sales"}
        </button>
      </div>
      {!canLoad && <div className="scope-note">Choose a city or zoom into a neighborhood to search a smaller area. <button type="button" onClick={onZoom}>Zoom into {areaLabel || "this area"}</button></div>}
      {state.loading && <p role="status">Checking recorded sales in this map area. This may take up to 20 seconds.</p>}
      {state.error && <div className="inline-alert" role="alert">{state.error.message}</div>}
      <Quota usage={state.usage} cached={state.cached} />
      {state.loaded && !state.error && <SalesEvidence sales={sales} state={state} areaLabel={areaLabel} />}
      <p className="fine-print">Sale events come from property records, not assessments. County recording delays may be weeks or months; owner fields are discarded before storage.</p>
      {!state.loading && !state.error && <PaginatedProperties rows={sales} kind="sales" dateKey="sale_date" empty={state.loaded ? "No sale events were returned for this area in the past year. Recording delays and provider coverage can leave gaps; this does not mean no homes sold. Try a nearby area or a tighter neighborhood view." : "Choose Search recent sales to check this map area."} />}
    </>
  );
}
