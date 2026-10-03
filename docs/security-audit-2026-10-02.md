# Security audit — 2026-10-02

## Outcome

The focused credential scan found no configured backend credential or common
secret signature in the reachable Git history, publishable working-tree files,
or generated frontend bundle. The five existing commits were already present
on `origin/main` when this work began. The scan is repeated after committing
this review and the walkthrough, before pushing.

Root and frontend `.env` files and the local database are ignored by Git and
have mode `0600`. The CARTO `VITE_` basemap key is intentionally browser-visible;
it is not a private backend credential. No environment file or local database
is included in this release.

This is a targeted source, history, configuration, and dependency review. It
does not establish that every possible vulnerability or credential format has
been eliminated.

## Findings fixed

- An unrelated website could send a simple, bodyless POST to the loopback
  refresh endpoint. CORS prevented reading the response but did not prevent
  the refresh itself. Protected provider/import endpoints now reject an
  `Origin` outside the configured frontend origin list or same local API
  origin, including `null`. Cross-site browser GETs without `Origin` are also
  rejected using Fetch Metadata before they can consume provider quota.
  Trusted local browser requests, API documentation, and CLI requests without
  `Origin` still work.
- FastAPI validation errors returned the string representation of validation
  failures, which includes submitted values. Responses now use fixed error
  messages, avoiding disclosure of invalid imported content.
- Listing and sale endpoint errors returned raw provider or validation
  exception strings. They now return fixed messages without upstream payload
  details, while preserving error codes and HTTP status.
- The local auditing environment contained urllib3 2.7.0 with three known
  advisories. It was upgraded to 2.8.0, and the repeat Python audit found no
  known vulnerabilities. urllib3 is used by the installed audit tooling; it
  is not a declared RealtyKit runtime dependency. See the upstream advisories
  for [chunk-size buffering](https://github.com/urllib3/urllib3/security/advisories/GHSA-vxq7-64xx-v4gw),
  [Deflate streaming](https://github.com/urllib3/urllib3/security/advisories/GHSA-gh4c-6fx4-qh6g),
  and [HTTPS proxy TLS](https://github.com/urllib3/urllib3/security/advisories/GHSA-8988-9cw3-xx77).

## Verification

- Backend: 77 tests passed, including nine security regression cases. No
  provider calls were made by those tests.
- Python lint: passed for `realtykit`, `tests`, and the credential scan script.
- Frontend: six chart-model tests passed; production build succeeded.
- npm lockfile audit: zero known vulnerabilities.
- Installed Python environment audit: zero known vulnerabilities after the
  upgrade; the editable `realtykit` package is not on PyPI and is inspected as
  local source rather than a published dependency.
- Credential scan: all reachable Git blobs, tracked and unignored new files,
  and `web/dist` files; exact matching for three locally configured backend
  secrets, plus private-key, GitHub, AWS, Slack, OpenAI, and credential-in-URL
  patterns. Secret values are never printed by the scanner.
- Request boundaries: existing loopback client/Host checks remain, CLI binding
  remains loopback-only, CORS origins are explicit, provider requests are
  bounded, and SQLite stores use parameterized queries.
- Walkthrough: recorded from the local app with paid provider credentials
  disabled; shows public boundaries and aggregate market data. No environment
  editor, terminal, credentials, or owner records appear in the media.

The existing Starlette TestClient deprecation and Vite bundle-size warnings
are unrelated to these security findings.

## Limits and continuing considerations

GitHub's secret-scanning alerts endpoint returned HTTP 403 for the available
credential. Hosted alert status could not be verified; this report does not
claim that GitHub has zero alerts.

The app remains intended for a single user's local machine. An `Origin`
header is a browser request boundary, not authentication against other local
processes. Python dependency ranges remain unlocked, so these audit results
apply to the installed versions at review time. Re-run audits after installing
or upgrading packages. Existing local cache and data protections and residual
considerations are recorded in the [previous review](security-audit-2026-09-02.md).

## Reproduce

From the repository root, after building the frontend:

```bash
.venv/bin/python scripts/security/scan_repository.py
.venv/bin/pytest -q
.venv/bin/ruff check realtykit tests scripts/security
.venv/bin/pip-audit --local --cache-dir /private/tmp/realtykit-audit-cache
cd web
npm run check
npm audit --cache /private/tmp/realtykit-npm-cache
```

Install `pip-audit` separately into a development environment if unavailable.
The scanner requires only Python's standard library and Git. It reports
locations and credential classes, never matching values. It excludes `VITE_`
values from exact backend-secret matching because those values are published
by design; private credentials must never be placed in `VITE_` variables.
