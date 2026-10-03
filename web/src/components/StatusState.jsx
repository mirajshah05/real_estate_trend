import { LoadingShip } from "./ThemeScene.jsx";

export function LoadingState({ label = "Loading" }) {
  return <div className="loading" role="status"><LoadingShip />{label}</div>;
}

export function ErrorState({ error, path }) {
  const status = error && error.status;
  const msg = (error && error.message) || "Request failed";
  return (
    <div className="error">
      {status === 404
        ? `Endpoint not available yet${path ? ` (${path})` : ""}.`
        : msg}
    </div>
  );
}

export function EmptyState({ children }) {
  return <div className="empty">{children}</div>;
}

export function OfflinePanel() {
  return (
    <div className="offline">
      <h2>API offline</h2>
      <p>
        The dashboard could not reach <code>GET /api</code> on port 8770, and
        no local fixtures are present under <code>/fixtures</code>.
      </p>
      <p>
        Start the API with <code>realtykit serve --port 8770</code>, then
        refresh. Market numbers are not invented while the API is down.
      </p>
    </div>
  );
}
