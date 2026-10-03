import { useEffect, useRef, useState } from "react";
import { getJson, postJson } from "../api.js";
import { referenceFilters, roomBounds } from "../propertyResults.js";
import SearchBox from "./SearchBox.jsx";
import { Quota } from "./PropertyTable.jsx";
import PaginatedProperties from "./PaginatedProperties.jsx";

const TYPES = ["Single Family", "Condo", "Townhouse", "Apartment", "Multi-Family", "Manufactured", "Land"];
const NUMBERS = [["min_price", "Minimum price ($)"], ["max_price", "Maximum price ($)"],
  ["min_sqft", "Minimum size (ft²)"], ["max_sqft", "Maximum size (ft²)"]];

export default function SimilarHomesPanel({ selected, cities }) {
  const [mode, setMode] = useState("requirements");
  const [area, setArea] = useState(selected?.geo_id !== "nation:US" ? selected : null);
  const [address, setAddress] = useState("");
  const [subject, setSubject] = useState(null);
  const [filters, setFilters] = useState({ intent: "buy", radius: "5", property_type: "", min_beds: "", min_baths: "", bed_match: "at_least", bath_match: "at_least", min_price: "", max_price: "", min_sqft: "", max_sqft: "" });
  const [status, setStatus] = useState(null);
  const [state, setState] = useState({ loading: false, error: null, result: null });
  const controller = useRef(null);
  const generation = useRef(0);
  const resultsTop = useRef(null);
  useEffect(() => {
    if (state.result) resultsTop.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [state.result]);
  useEffect(() => {
    const abort = new AbortController();
    getJson("/api/homes/status", { signal: abort.signal }).then(setStatus).catch(error => {
      if (error.name !== "AbortError") setState(s => ({ ...s, error }));
    });
    return () => { abort.abort(); controller.current?.abort(); };
  }, []);

  function invalidate() {
    generation.current += 1;
    controller.current?.abort();
    setState({ loading: false, error: null, result: null });
  }
  function update(key, value) {
    invalidate();
    setFilters(current => ({ ...current, ...(key === "intent" ? { min_price: "", max_price: "" } : {}), [key]: value }));
  }
  async function request(path, body, accept) {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const id = ++generation.current;
    setState({ loading: true, error: null, result: null });
    try {
      const data = await postJson(path, body, { signal: abort.signal });
      if (id !== generation.current) return;
      setStatus(s => ({ ...s, usage: data.usage }));
      accept(data);
    } catch (error) {
      if (id === generation.current && error.name !== "AbortError") setState({ loading: false, error, result: null });
    }
  }
  async function lookup(event) {
    event.preventDefault();
    await request("/api/homes/subject", { address }, data => {
      const p = data.property;
      setSubject(p);
      setFilters(f => ({ ...f, ...referenceFilters(p), property_type: TYPES.includes(p.property_type) ? p.property_type : "" }));
      setState({ loading: false, error: null, result: null });
    });
  }
  async function search(event) {
    event.preventDefault();
    const center = mode === "address" ? subject : area;
    if (!center) return;
    const body = { lat: center.lat, lon: center.lon, intent: filters.intent, radius: Number(filters.radius), property_type: filters.property_type || null, ...roomBounds(filters) };
    for (const [key] of NUMBERS) body[key] = filters[key] === "" ? null : Number(filters[key]);
    if ((body.min_price != null && body.max_price != null && body.min_price > body.max_price) ||
        (body.min_sqft != null && body.max_sqft != null && body.min_sqft > body.max_sqft)) {
      setState({ loading: false, error: { message: "Minimum price and size must be no greater than their maximums." }, result: null });
      return;
    }
    if (mode === "address") body.exclude_property_id = subject.property_id;
    await request("/api/homes/search", body, result => setState({ loading: false, error: null, result }));
  }
  const center = mode === "address" ? subject : area;
  const disabled = state.loading || status?.configured === false;
  return (
    <section className="home-search">
      <h2>Find similar homes</h2>
      <p className="panel-caption">Start with an address or tell us what you need. Search active homes for sale or long-term rentals near your location.</p>
      <div className="subtabs" aria-label="Search starting point">
        {[["requirements", "By requirements"], ["address", "From an address"]].map(([id, label]) =>
          <button key={id} type="button" aria-pressed={mode === id} className={mode === id ? "active" : ""} onClick={() => { invalidate(); setMode(id); }}>{label}</button>)}
      </div>
      {status?.configured === false && <div className="inline-alert" role="alert">RentCast is not configured in the running backend. Add your API key to the local configuration and restart the backend.</div>}
      {mode === "requirements" ? <div className="home-area">
        <label>Search location</label>
        <SearchBox cities={cities} selectedId={area?.geo_id} onSelect={place => { invalidate(); setArea(place); }} />
        <p>{area ? `Searching near ${area.name}${area.state && !area.name.endsWith(`, ${area.state}`) ? `, ${area.state}` : ""}` : "Choose a city or ZIP to set the center of your search."}</p>
        {area && !["city", "zip", "address"].includes(area.kind) && <p className="fine-print">This location is a metro-area center. Choose a ZIP or reference address for a more precise neighborhood search.</p>}
      </div> : <form className="home-address" onSubmit={lookup}>
        <label className="field">Reference home address
          <input required minLength={8} maxLength={250} value={address} placeholder="Street, city, state, ZIP (and unit)" onChange={event => { invalidate(); setSubject(null); setAddress(event.target.value); }} />
        </label>
        <button type="submit" disabled={disabled}>{state.loading && !subject ? "Looking up…" : "Look up home"}</button>
        {subject && <div className="reference-summary">
          <span className="eyebrow">Provider reference facts · review before searching</span>
          <strong>{subject.address}</strong>
          <p>{subject.property_type || "Home type unknown"} · {subject.beds == null ? "Bedrooms unknown" : `${subject.beds} bedrooms`} · {subject.baths == null ? "Bathrooms unknown" : `${subject.baths} bathrooms`}{subject.sqft ? ` · ${subject.sqft.toLocaleString()} ft²` : ""}</p>
          <p className="fine-print">Reference facts from RentCast property records. Bedrooms and bathrooms default to exact matches; size defaults to ±20%. If a fact is incorrect or missing, adjust the filters below. The reference home is excluded.</p>
          {((filters.min_beds !== "" && subject.beds != null && Number(filters.min_beds) !== subject.beds) || (filters.min_baths !== "" && subject.baths != null && Number(filters.min_baths) !== subject.baths)) && <p className="reference-correction">Your room counts override the provider reference facts. Matching uses your {filters.min_beds || "any"}-bedroom and {filters.min_baths || "any"}-bathroom choices below.</p>}
        </div>}
      </form>}
      <form onSubmit={search}>
        <div className="home-search-fields">
          <label className="field">I want to<select value={filters.intent} onChange={event => update("intent", event.target.value)}><option value="buy">Buy a home</option><option value="rent">Rent a home</option></select></label>
          <label className="field">Within (miles)<input type="number" min="0.1" max="25" step="0.1" required value={filters.radius} onChange={event => update("radius", event.target.value)} /></label>
          <label className="field">Home type<select value={filters.property_type} onChange={event => update("property_type", event.target.value)}><option value="">Any home type</option>{TYPES.map(type => <option key={type}>{type}</option>)}</select></label>
          {[["min_beds", "bed_match", "Bedrooms", "1"], ["min_baths", "bath_match", "Bathrooms", "0.5"]].map(([number, match, label, step]) => <fieldset className="room-filter" key={number}>
            <legend>{label}</legend>
            <input aria-label={label} type="number" min="0" max="20" step={step} value={filters[number]} placeholder="Any" onChange={event => update(number, event.target.value)} />
            <select aria-label={`${label} matching`} value={filters[match]} onChange={event => update(match, event.target.value)}><option value="exact">Exactly</option><option value="at_least">At least</option></select>
          </fieldset>)}
          {NUMBERS.map(([key, label]) => <label key={key} className="field">{filters.intent === "rent" && key.includes("price") ? `${label} / month` : label}<input type="number" min={key.startsWith("max_") ? "1" : "0"} max={key.includes("beds") || key.includes("baths") ? "20" : key.includes("sqft") ? "100000" : "100000000"} step={key.includes("baths") || key.includes("beds") ? "0.5" : "1"} value={filters[key]} placeholder="No preference" onChange={event => update(key, event.target.value)} /></label>)}
        </div>
        <button className="primary-action" type="submit" disabled={disabled || !center}>{state.loading ? "Searching…" : "Search matching homes"}</button>
        {!center && <p className="panel-caption">{mode === "address" ? "Look up a reference home first." : "Select a search location first."}</p>}
      </form>
      <div className="matching-summary">
        <strong>How homes are selected</strong>
        <p>Active {filters.intent === "rent" ? "rentals" : "sale listings"} within {filters.radius || "your chosen"} miles
          {filters.property_type ? ` · ${filters.property_type}` : " · any home type"}
          {filters.min_beds !== "" ? ` · ${filters.bed_match === "exact" ? "exactly" : "at least"} ${filters.min_beds} bedrooms` : " · any bedrooms"}
          {filters.min_baths !== "" ? ` · ${filters.bath_match === "exact" ? "exactly" : "at least"} ${filters.min_baths} bathrooms` : " · any bathrooms"}.</p>
        <p className="fine-print">Budget and size limits also apply. Records missing a required fact are excluded. We never automatically relax your filters. Results start nearest first within the returned sample.</p>
      </div>
      <p className="fine-print">Each uncached lookup or search uses one RentCast request. Searches reuse a six-hour cache. Listing coverage and availability vary by area.</p>
      <Quota usage={status?.usage} cached={state.result?.cached} />
      {state.loading && <p role="status">Checking RentCast. This can take up to 20 seconds.</p>}
      {state.error && <div className="inline-alert" role="alert">{state.error.message}</div>}
      {state.result && <div aria-live="polite" ref={resultsTop} className="home-results">
        <h3>{state.result.listings.length} matching {filters.intent === "rent" ? "rentals" : "homes for sale"} in this sample</h3>
        <p className="results-criteria">{mode === "address" ? `Near ${subject.address}` : `Near ${area.name}`} · {filters.radius} miles · {filters.property_type || "Any home type"}{filters.min_beds !== "" ? ` · ${filters.bed_match === "exact" ? "exactly" : "at least"} ${filters.min_beds} bedrooms` : ""}{filters.min_baths !== "" ? ` · ${filters.bath_match === "exact" ? "exactly" : "at least"} ${filters.min_baths} bathrooms` : ""}</p>
        <p className="panel-caption">{state.result.note}</p>
        {state.result.possibly_truncated && <p className="scope-note">This search reached the provider’s 100-record page limit. Narrow the radius or filters to reduce missed matches.</p>}
        <PaginatedProperties rows={state.result.listings} dateKey="as_of" empty="No active homes met these filters in the returned records. Try a wider radius, a higher budget, or choose At least for bedrooms or bathrooms, then search again." />
      </div>}
    </section>
  );
}
