import { useEffect, useMemo, useRef, useState } from "react";
import { propertyPage } from "../propertyResults.js";
import { PropertyRows } from "./PropertyRows.jsx";

export default function PaginatedProperties({ rows, dateKey, empty, kind = "homes" }) {
  const [sort, setSort] = useState(kind === "sales" ? "recent" : "nearest");
  const [page, setPage] = useState(1);
  const top = useRef(null);
  useEffect(() => setPage(1), [rows]);
  const result = useMemo(() => propertyPage(rows, { sort, page }), [rows, sort, page]);
  const noun = kind === "sales" ? "sale events" : "homes";
  function changePage(next) {
    setPage(next);
    top.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }
  function pager(position) {
    if (result.pages <= 1) return null;
    return <nav className="property-pagination" aria-label={`${noun} pages (${position})`}>
      <button type="button" disabled={result.page === 1} onClick={() => changePage(result.page - 1)}>Previous</button>
      <label>Page <select aria-label={`Results page (${position})`} value={result.page} onChange={event => changePage(Number(event.target.value))}>
        {Array.from({ length: result.pages }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}
      </select> of {result.pages}</label>
      <button type="button" disabled={result.page === result.pages} onClick={() => changePage(result.page + 1)}>Next</button>
    </nav>;
  }
  if (!rows.length) return <PropertyRows rows={[]} dateKey={dateKey} empty={empty} />;
  return <section className="paginated-properties" ref={top} aria-label={`${noun} results`}>
    <div className="results-toolbar">
      <p role="status">Showing {result.first}–{result.last} of {result.total} {noun} · 10 per page</p>
      <label className="field">Sort results<select aria-label="Sort results" value={sort} onChange={event => { setSort(event.target.value); setPage(1); }}>
        <option value={kind === "sales" ? "recent" : "nearest"}>{kind === "sales" ? "Most recent sale" : "Nearest first"}</option>
        <option value="price_asc">Price: low to high</option>
        <option value="price_desc">Price: high to low</option>
      </select></label>
    </div>
    <p className="fine-print">Sorting and paging apply to these {result.total} loaded {noun}; they do not make additional provider requests. Unknown prices appear last.</p>
    {pager("top")}
    <PropertyRows rows={result.rows} dateKey={dateKey} empty={empty} />
    {pager("bottom")}
  </section>;
}
