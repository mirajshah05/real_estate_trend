export default function TaskLanding({ selected, onTab }) {
  const local = selected && selected.geo_id !== "nation:US";
  return <section className="task-landing">
    <span className="eyebrow">{local ? "Your next step" : "Start here"}</span>
    <h2>{local ? `Explore ${selected.name}` : "What would you like to find?"}</h2>
    <p className="panel-caption">{local ? "Your location is selected. Choose a task below to continue." : "Search a city or click a map circle, then choose a task. You can also start with a home address."}</p>
    <div className="task-cards">
      <button type="button" className="task-card" onClick={() => onTab("similar")}><strong>Find similar homes <span>→</span></strong><span>Use an address or your budget, bedrooms and size to find homes for sale or rent.</span></button>
      <button type="button" className="task-card" onClick={() => onTab("rentals")}><strong>Rent intelligence <span>→</span></strong><span>Explore rental trends and estimate rent. Historical coverage: San Jose, Sunnyvale, Mountain View and Palo Alto.</span></button>
      <button type="button" className="task-card" onClick={() => onTab("trends")}><strong>Market trends <span>→</span></strong><span>See home values, inventory and how long homes take to sell in this market.</span></button>
      <button type="button" className="task-card" onClick={() => onTab("sales")}><strong>Recent sales <span>→</span></strong><span>Search recorded property sales from the past year in the visible map area.</span></button>
    </div>
    <p className="scope-note"><strong>Reading the map</strong><br />Each circle represents a metro market. Red means a decrease; blue means an increase. Larger circles mean a larger change. Home value uses Zillow’s typical-home estimate (ZHVI), not an individual listing price.</p>
  </section>;
}
