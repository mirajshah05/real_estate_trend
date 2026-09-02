# Security audit — 2026-09-02

## Outcome

No configured credential was found in the tracked repository, any of its three
reachable commits, or GitHub secret-scanning alerts. Root and frontend `.env`
files are ignored and mode `0600`; real key values are not present in examples,
documentation, source, or the browser bundle.

The audit covered all reachable Git blobs, common secret signatures, exact
matches for locally configured credentials, tracked/ignored files, Python and
npm advisories, network exposure, CORS, provider request paths, logs, database
permissions, and GitHub security status.

## Remediation completed

- Upgraded React Router to 7.18.3 and Vite to 6.4.3; `npm audit` reports zero
  known vulnerabilities.
- Sanitized URL query secrets and bearer tokens in structured logs. FRED API
  failures now log exception type/status rather than a URL containing its key.
- Added loopback client and Host checks to quota-consuming provider endpoints;
  the CLI continues to reject non-loopback binds.
- Added atomic in-flight reservations before RentCast calls, a 45-request
  warning, and a hard 50-successful-request local cap.
- Restricted the SQLite database and sidecars to mode `0600`.
- Expanded `.gitignore` for `.envrc`, private SSH key names, service-account
  files, secret YAML files, and SQLite 3 databases.
- Sanitized RentCast property responses before caching: owner, mailing,
  assessment, and tax fields are neither returned nor stored.

## Residual considerations

- The app is intentionally local-only and does not implement user accounts.
  Do not expose Uvicorn or Vite to a public/network interface without adding
  authentication, authorization, TLS, CSRF protection, and production rate
  limiting.
- The persistent usage counter knows only calls made by this local database.
  Provider dashboards remain authoritative for account-wide usage.
- Python dependency ranges are not locked, so future clean installs are not
  deterministic. Add a reviewed lockfile before production deployment.
- GitHub Dependabot alerts/security updates and CodeQL analysis were not
  enabled at audit time. Enabling them is recommended for ongoing monitoring.
- Address-level records are sensitive local research data even though they are
  public property facts. Keep `data/` untracked, preserve mode `0600`, and add
  a retention policy before multi-user or production use.
- CARTO's `VITE_` basemap key is client-visible by design. Apply provider-side
  origin restrictions and monitor its usage; never put private provider keys
  in any `VITE_` variable.

## Reproduce

```bash
git status --short
git check-ignore -v .env web/.env data/realtykit.db
.venv/bin/pip-audit --local
cd web && npm audit --audit-level=low && npm run build
cd .. && .venv/bin/pytest -q
```

Do not print environment files or inject their contents into command lines when
running additional scans.
