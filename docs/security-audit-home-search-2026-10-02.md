# Home search release security and privacy review — 2026-10-02

## Scope and outcome

Pre-commit review of similar-home search, task navigation, result pagination and
sorting, sale provenance, and the accompanying product/data-source research.
The configured Git remote is `mirajshah05/real_estate_trend`.

No configured backend credential or supported secret signature was found in
publishable files, reachable Git blobs, or the generated frontend bundle.
Python and npm dependency audits reported no known vulnerabilities. These are
focused checks of the current source and installed/locked dependencies, not a
guarantee against every vulnerability or form of personal data.

## Privacy and request boundaries

- Removed personal workstation paths from the new research notes; repository
  links now use relative paths and generated outputs use repository-local names.
- Reviewed all 38 changed/new files before adding this report for personal paths,
  the user's supplied reference address, SSN patterns, email addresses and phone
  numbers. The only contact candidates were the cited Santa Clara Assessor
  business phone and Bridge's published API support email. No user reference
  address, owner names, personal contact information or downloaded raw records
  are included in these changes. Test records use synthetic placeholders.
- `.env`, `web/.env`, the local SQLite database and `data/research/` downloads
  are ignored and untracked. Both environment files and the local database
  have mode `0600`. Raw state downloads may contain personal information and
  remain local; the committed research script emits aggregate statistics only.
- Address lookup intentionally sends the submitted address to RentCast and
  caches an allowlist of property facts for 24 hours in the local database.
  Listing matches use a six-hour local cache. Owner, agent and contact fields
  are discarded before caching or returning results.
- Both new home endpoints use existing loopback client/Host checks and reject
  foreign/null origins and cross-site Fetch Metadata requests before provider
  calls. The shared monthly request cap remains enforced server-side.
- Provider URLs are fixed; inputs have bounded coordinates, radius, lengths,
  values and ordered ranges. Errors use fixed messages rather than echoing
  request bodies, keys or upstream error payloads. React renders property data
  as text; new components introduce no HTML injection sinks or browser storage.
- Paging and sorting operate on the retrieved sample without extra provider
  calls. Sale provenance keeps only the provider property ID and normalized
  event origin, rather than raw records or owner/assessment payloads.

## Verification

- Backend: **94 tests passed**, including subject-cache privacy checks and
  foreign-origin/cross-site rejection for both home-search endpoints.
- Frontend: **11 tests passed**, and the production build succeeded.
- Ruff: passed for `realtykit`, `tests`, `scripts/security`, and `scripts/research`.
- npm package-lock audit: **zero known vulnerabilities**.
- Installed Python environment audit: **zero known vulnerabilities**; the local
  editable `realtykit` project is reviewed as source and is not on PyPI.
- Credential scanner: **zero findings**, covering reachable Git history,
  tracked/unignored files, and the frontend build. It checks exact configured
  backend secrets and common private-key, GitHub, AWS, Slack, OpenAI and
  credential-in-URL signatures without printing matching values. The intentional
  public `VITE_` basemap configuration is separate from private backend keys.
- `git diff --check`: passed. The credential scanner is repeated on the final
  staged tree and committed files before pushing.

## Reproduce

```sh
.venv/bin/pytest -q
.venv/bin/ruff check realtykit tests scripts/security scripts/research
.venv/bin/pip-audit --local --cache-dir /private/tmp/realtykit-audit-cache
cd web
npm run check
npm audit --package-lock-only --registry=https://registry.npmjs.org --cache /private/tmp/realtykit-npm-cache --userconfig=/dev/null
cd ..
.venv/bin/python scripts/security/scan_repository.py
git diff --check
```

The existing local-only deployment model and broader audit limitations remain
documented in [the preceding review](security-audit-2026-10-02.md). This review
does not verify GitHub-hosted security alert status or scan local raw research
records for publication: those records are excluded from this commit.
