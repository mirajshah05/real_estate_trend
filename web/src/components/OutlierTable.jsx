import { formatSigned } from "../normalize.js";
import { EmptyState } from "./StatusState.jsx";

export default function OutlierTable({ rows, selectedId, onSelect }) {
  if (!rows.length) {
    return <EmptyState>Home-level outliers need a listing API key.</EmptyState>;
  }

  return (
    <>
      <table className="table">
        <thead>
          <tr>
            <th>Metro</th>
            <th>Score</th>
            <th>As of</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.subject_id || r.name}
              className={r.subject_id === selectedId ? "selected" : ""}
              onClick={() => onSelect && onSelect(r.subject_id)}
              style={{ cursor: onSelect ? "pointer" : "default" }}
            >
              <td>
                {r.name}
                {r.reasons.length > 0 && (
                  <div className="reasons">{r.reasons.join("; ")}</div>
                )}
              </td>
              <td>{formatSigned(r.score)}</td>
              <td>{r.as_of || "—"}</td>
              <td>{r.source || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="panel-caption">
        Market outliers (metro grain). Home-level outliers need a listing API key.
      </p>
    </>
  );
}
