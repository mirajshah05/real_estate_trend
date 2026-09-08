# Historical Bay Area rental data

RealtyKit accepts local CSV or JSON exports containing up to three years of
rental observations for San Jose, Sunnyvale, Mountain View, and Palo Alto. The
import is intended for data that the user is licensed or otherwise permitted to
store and analyze. RealtyKit does not claim that user-supplied source labels are
verified provider provenance.

## Import API

`POST /api/rentals/import` is loopback-only and accepts JSON:

```json
{
  "filename": "my-rental-export.csv",
  "format": "csv",
  "content": "observed_on,city,monthly_rent,bedrooms,property_type,listing_status\n2026-08-15,San Jose,3400,1,apartment,new\n"
}
```

The server accepts the file contents, not a filesystem path. Limits are 5 MiB
of UTF-8 text and 25,000 rows per request. The filename must be a basename whose
extension matches `format`. CSV headers and JSON row keys use the same schema:

| Field | Required | Accepted value |
|---|---:|---|
| `observation_id` | No | Stable source ID; otherwise RealtyKit derives a content-based ID |
| `source` | No | User-supplied provenance label; defaults to `local_upload` |
| `observed_on` | Yes | ISO date no later than today and no earlier than the same calendar date three years ago |
| `city` | Yes | `San Jose`, `Sunnyvale`, `Mountain View`, or `Palo Alto` |
| `monthly_rent` | Yes | Number greater than 0 and no greater than 100,000 |
| `bedrooms` | Yes | `1`, `2`, or `3` |
| `property_type` | Yes | `apartment`, `townhouse`, or `single_family` |
| `listing_status` | Yes | `new` or `existing` |
| `availability_status` | No | `active`, `inactive`, or `unknown`; defaults to `unknown` |
| `zip_code` | No | Five digits |
| `neighborhood` | No | Printable text, up to 100 characters |
| `bathrooms` | No | 0 through 20 |
| `sqft` | No | 100 through 30,000 |
| `year_built` | No | 1800 through the current year plus one |
| `amenities` | No | JSON string array, or a pipe-delimited value in CSV, up to 24 entries |
| `latitude`, `longitude` | No | Valid coordinates |
| `removed_on`, `last_seen_on` | No | ISO dates on or after `observed_on`, no later than today |

Common input aliases are normalized: `townhome` becomes `townhouse`, `sfh`
becomes `single_family`, and `old` becomes `existing`. Unknown columns, invalid
rows, duplicate IDs within one upload, non-finite numbers, and out-of-scope
cities are rejected. Validation is atomic: if one row is invalid, no observation
from the upload is written. At most 50 row errors are returned.

The normalized observations retain `import_id`, source label, and import time.
An `observation_id` identifies one observation event, not a property or listing
across time. Re-importing the same ID can correct that event's attributes, but
cannot change its source, city, or observation date; use a different ID for a
later monthly snapshot. Raw upload contents are not retained.

## Query APIs

`GET /api/rentals/trends?city=San%20Jose&months=36` returns monthly segments
grouped by bedroom count, property type, listing-age status, and availability
status. Each segment has
count, exact median, average, minimum, and maximum asking rent. The UI offers
12-, 24-, and 36-month windows; a requested window includes the month containing
the latest matching observation plus the preceding calendar months.
`as_of=YYYY-MM-DD` can pin the end date. Optional
`bedrooms`, `property_type`, and `listing_status` filters narrow the result.
`availability_status=active|inactive|unknown` can also narrow it.

`GET /api/rentals/observations` returns normalized rows for inspection, with
optional `city`, `limit`, and `offset` parameters. Both query endpoints are also
loopback-only because imported data may be private.

For user uploads, `listing_status` describes the classification present in the
uploaded source; RealtyKit does not infer it. For RentCast collection only, it
is explicitly a listing-age bucket: `new` means 30 or fewer provider-reported
days on market and `existing` means more than 30. It does not describe a new or
incumbent tenant. `availability_status` separately preserves the provider's
active/inactive state. Rent statistics are asking-rent summaries, not
signed-lease prices, appraisals, or investment advice.

## Bounded provider collection

The configured RentCast key can collect one page for each selected city/status
pair from its official long-term rental listings endpoint. The default command
requests at most 100 records for each of four cities and two statuses (eight
requests maximum), with provider-side filters for 1-3 bedrooms, Apartment,
Townhouse, and Single Family, and listings no more than 1,095 days old:

```bash
realtykit ingest rentals --providers rentcast
```

Use a smaller probe without fanning out:

```bash
realtykit ingest rentals --providers rentcast --cities "San Jose" --statuses active --limit-per-query 25
```

Every outbound RentCast attempt is atomically recorded before sending, including
failed HTTP attempts. The persistent local hard cap is 40 attempts per UTC
calendar month and cannot be raised through environment configuration. Cached
responses are reused for 24 hours unless `--force` is explicitly requested.
The cache contains only the normalized rows; contacts, office/builder details,
MLS metadata, raw history objects, and exact street addresses are discarded.

The collector expands RentCast `Rental Listing` history entries when present,
but one bounded result page is not an exhaustive city census. Re-running it can
update known observation events and discover newer events.

On September 7, 2026, one quota-counted San Jose/active verification request
returned HTTP 200. A page capped at 25 provider records expanded to 32 sanitized
current/history observation events dated September 26, 2024 through September
7, 2026. The persistent ledger then showed 7 attempted requests, 1 successful
request, 0 reserved, and 33 remaining under the hard cap. This is a local cache
snapshot, not a promise of future API availability or complete city coverage.

## Official public ZORI index lane

Zillow Research publishes historical ZORI asking-rent indices, including the
city-level all-homes file at
`https://files.zillowstatic.com/research/public_csvs/zori/City_zori_uc_sfrcondomfr_sm_month.csv`.
`realtykit ingest refresh --providers zillow` includes this source, and the
rental-only command is:

```bash
realtykit ingest rentals --providers zillow
```

The adapter stores only the last three years for the four target California
cities in aggregate `market_facts`, with source URL, SHA-256, download clock,
and observation clock. Downloads are capped at 20 MiB. It does not insert ZORI
into property observations.
`GET /api/rentals/trends` exposes it in a separate `market_indices` block with
provider, source ID, as-of date, `home_type=all_homes`, and monthly points.
The Rentals view uses this series for a data-focused rent axis and matching-month
summer comparisons. Seasonal summaries use complete years when possible and are
explicitly marked partial when the current summer is incomplete.

The city ZORI series cannot honestly supply individual listings,
new-versus-existing classification, townhouse-only cuts, or 1/2/3-bedroom cuts
unless a specific published source provides those dimensions. Those dimensions
remain upload-only in the current feature.

The September 7, 2026 collection cached the official 4.6 MiB file and stored
140 filtered facts: 35 monthly all-homes ZORI points for each target city, from
September 30, 2023 through the publisher's July 31, 2026 observation date.
