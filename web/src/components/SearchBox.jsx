import { useEffect, useMemo, useState } from "react";
import { getApiOrFixture, paths } from "../api.js";

export default function SearchBox({ cities, onSelect, selectedId }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [remoteHits, setRemoteHits] = useState([]);

  useEffect(() => {
    const query = q.trim();
    if (query.length < 3) {
      setRemoteHits([]);
      return undefined;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      const response = await getApiOrFixture(paths.search(query));
      if (!cancelled && response.data) setRemoteHits(response.data.results || []);
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [q]);

  const hits = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return cities.slice(0, 8);
    const local = cities
      .filter((c) => `${c.name} ${c.state} ${c.geo_id}`.toLowerCase().includes(needle))
      .slice(0, 12);
    const merged = [...local, ...remoteHits];
    const seen = new Set();
    return merged.filter((c) => {
      const key = `${c.geo_id}|${c.label || c.name}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 12);
  }, [cities, q, remoteHits]);

  return (
    <div className="search-box">
      <input
        type="search"
        placeholder="Search city, ZIP, or address"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
          if (e.key === "Enter" && hits[0]) {
            onSelect(hits[0]);
            setQ(hits[0].label || hits[0].name);
            setOpen(false);
          }
        }}
        aria-label="Search city, ZIP, or address"
      />
      {open && hits.length > 0 && (
        <ul>
          {hits.map((c) => (
            <li key={c.geo_id || `${c.name}-${c.lat}`}>
              <button
                type="button"
                className={c.geo_id === selectedId ? "active" : ""}
                onClick={() => {
                  onSelect(c);
                  setQ(c.label || c.name);
                  setOpen(false);
                }}
              >
                {c.label || c.name}
                {!c.label && c.state ? `, ${c.state}` : ""}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
