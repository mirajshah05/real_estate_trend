# Property-level listing and sold prices in the Bay Area

Research verified on **2026-09-01** for Palo Alto, Mountain View, Sunnyvale,
San Jose, Santa Clara, and adjacent San Mateo County communities.

## Implementation status — 2026-09-02

- RealtyKit now implements `/api/map/listings` and `/api/map/sales` through
  RentCast, with six-hour/24-hour persistent caches respectively.
- Sale records are normalized into `sale_events`; owner, mailing, assessment,
  and tax fields are discarded before any response or cache write.
- Every RentCast attempt is reserved atomically in the offline SQLite ledger,
  warns at 32/40, and is blocked at 40. Environment settings may lower the
  limit but cannot raise it. The account-wide provider dashboard remains the
  authority for calls made outside this app.
- The supplied RentCast key returned HTTP 403 on the official endpoint because
  it is not associated with an active API subscription. The supplied ATTOM key
  returned HTTP 401 while its trial application remained Pending. Both tests
  were non-successful; neither produced property data.
- The UI now distinguishes city boundaries from the San Jose metro aggregate.
  For example, Sunnyvale's 247 new listings is the metro-wide weekly Zillow
  observation, not a downloadable set of 247 Sunnyvale addresses.

## Decision

Use separate acquisition lanes because a listing price and a recorded sale
price are different facts with different publishers:

1. **Immediate development path — RentCast:** one self-serve API key supplies
   current and inactive sale listings plus property sale histories. The free
   Developer plan includes 50 requests per month, but RealtyKit deliberately
   stops at 40 attempted requests for a safety buffer. This is enough for
   integration testing but not a scheduled production refresh.
2. **Production listing path — MLSListings:** obtain an authorized IDX, VOW, or
   other licensed data feed through a participating broker. MLSListings is the
   local MLS for Santa Clara and San Mateo counties, refreshes every five
   minutes, and tracks listings through close with the final sold price.
3. **Official sold-price validation — verified county transfer lists:** import
   Santa Clara's documented two-year sales list into `sale_events`. Treat San
   Mateo's fee-page entry as an unverified lead until a sample and data
   dictionary prove that it contains transaction consideration rather than
   assessment-only fields.
4. **Commercial recorded-sale fallback — ATTOM:** use only if RentCast coverage
   testing is insufficient and ATTOM's contract, retention, and display terms
   fit the application.

Do not scrape Zillow, Redfin, Compass, MLSListings, assessor search pages, or
recorder portals. Their public websites are not substitutes for licensed or
official machine-readable feeds.

## Geographic coverage

| Area | County | Primary listing source | Official sold-price path |
|---|---|---|---|
| Palo Alto | Santa Clara | RentCast now; MLSListings when licensed | Santa Clara two-year sales list |
| Mountain View | Santa Clara | RentCast now; MLSListings when licensed | Santa Clara two-year sales list |
| Sunnyvale | Santa Clara | RentCast now; MLSListings when licensed | Santa Clara two-year sales list |
| San Jose | Santa Clara | RentCast now; MLSListings when licensed | Santa Clara two-year sales list |
| Santa Clara | Santa Clara | RentCast now; MLSListings when licensed | Santa Clara two-year sales list |
| Menlo Park, Redwood City, San Mateo, and adjacent peninsula cities | San Mateo | RentCast now; MLSListings when licensed | Unverified county fee product; vendor/MLS until fields are confirmed |

All five named South Bay cities are in Santa Clara County. San Mateo County
parcel and sales files are useful for adjacent peninsula coverage but cannot
replace Santa Clara records.

## Source matrix

### RentCast: fastest path with one key

- Account and key: [RentCast API dashboard](https://app.rentcast.io/app/api)
- Documentation: [API introduction](https://developers.rentcast.io/reference/introduction)
- Listing endpoint: `GET https://api.rentcast.io/v1/listings/sale`
- Sold/property endpoint: `GET https://api.rentcast.io/v1/properties`
- Authentication: `X-Api-Key: ${RENTCAST_API_KEY}`
- Pagination: `limit` up to 500 plus `offset`
- Provider allowance: 50 requests per month on the Developer plan; RealtyKit's
  local hard cap is 40 attempts per calendar month
- Listing freshness: RentCast says each listing is updated at least daily and
  newly published listings are generally available within 12–24 hours.
- Coverage claim: RentCast says it targets at least 96% residential listing
  coverage nationally. This must be measured for the selected cities before it
  is treated as complete local coverage.

Current listings by city:

```http
GET /v1/listings/sale?city=Palo%20Alto&state=CA&status=Active&limit=500&offset=0
X-Api-Key: ${RENTCAST_API_KEY}
```

Recent sold properties by city:

```http
GET /v1/properties?city=Palo%20Alto&state=CA&saleDateRange=14&limit=500&offset=0
X-Api-Key: ${RENTCAST_API_KEY}
```

Specific property by normalized full address:

```http
GET /v1/properties?address=123%20Example%20St%2C%20Palo%20Alto%2C%20CA%2C%2094301
X-Api-Key: ${RENTCAST_API_KEY}
```

The property response includes a `history` object keyed by date; sale entries
contain `event`, `date`, and `price`. The listing response includes `price`,
`status`, `listedDate`, `removedDate`, `lastSeenDate`, `daysOnMarket`,
coordinates, MLS identifiers when available, and listing-price history.

The existing RealtyKit connector already maps active RentCast listings. The
next code change should add `/properties` ingestion and preserve the two price
kinds as `list_price` and `sale_price`; it must not overwrite one with the
other.

### MLSListings: authoritative local listing and close data

- Coverage and cadence: [MLSListings describes Santa Clara and San Mateo as
  core counties](https://www.mlslistings.com/about-us/about-mlslistings/support)
  and says its data refreshes every five minutes.
- Data-feed application: [MLSListings Data/IDX](https://supportlwr.mlslistings.com/data-idx)
- Contact: `data@mlslistings.com`
- Access: an MLS Participant Broker applies for the appropriate IDX, VOW, or
  other authorized feed and approves the application/vendor.
- Transport: request the current RESO Web API option and its metadata endpoint;
  RESO is a standard, not a data provider. Credentials come from MLSListings or
  its designated API vendor after the data-use agreement is approved.

Minimum RESO fields to request:

| RealtyKit field | RESO field |
|---|---|
| provider listing ID | `ListingKey` |
| MLS number | `ListingId` |
| status | `StandardStatus` |
| list price | `ListPrice` |
| original list price | `OriginalListPrice` |
| close price | `ClosePrice` |
| listing date | `OnMarketDate` |
| close date | `CloseDate` |
| last source update | `ModificationTimestamp` |
| address | `UnparsedAddress`, city/state/postal fields |
| coordinates | `Latitude`, `Longitude` |
| property facts | bedrooms, bathrooms, living area, lot size, year built |

The licensed use controls which statuses and fields may be stored or displayed.
IDX is intended for public listing display; closed/sold history may require VOW,
broker back-office, or another agreement. The application must not assume that
receiving `ClosePrice` grants permission to display it publicly.

### Santa Clara County: official indicated sale prices

California [Revenue and Taxation Code section
408.1](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=RTC&sectionNum=408.1)
requires county assessors to maintain a geographically divided list of property
transfers from the preceding two years, revise it quarterly, and include APN,
address, transfer date, recording date/reference, and consideration when known.

The [Santa Clara County Assessor FAQ](https://www.sccassessor.org/faq/understanding-proposition-13%3A)
describes its list as the **inspection of the two-year sales list**. It is
currently supplied on microfiche, organized by APN, updated quarterly, and
contains transferee, property address, transfer date, document number,
transferor, recording date, indicated sales price, and land-use code. The
published fee schedule lists a $10 inspection fee. Contact the Assessor at
`assessor@asr.sccgov.org` or `408-299-5500` and request:

- an electronic CSV/fixed-width delivery or recurring export, if available;
- only the five target cities or their APN ranges;
- the latest two-year list and its data-as-of date;
- permission and terms for automated internal use and public display;
- a data dictionary for land-use and transfer/sale codes.

The public statute guarantees inspection, not an API or electronic bulk file.
Until the county confirms an electronic delivery, this source must be labeled
`manual_import`, `quarterly`, and unsuitable for the seven-day freshness SLA.

### San Mateo County: unverified fee-page lead

San Mateo County publishes an [Assessment Data Fees](https://smcacre.gov/assessor/assessment-data-fees)
page listing **Property Sales History — $305**, but that fee-page label does
not document the product's fields and does not establish that actual sale
consideration is included. It must not be represented as a confirmed source of
sold-house prices. Before purchasing, contact the Assessor at `650-363-4500`
and request a sample plus data dictionary, format, observation date, update
cadence, reuse terms, and an explicit answer about recorded consideration.

The Recorder maintains public transaction documents and collects documentary
transfer tax, but transfer tax is not a safe universal sale-price field: liens,
exemptions, and non-sale transfers can make a derived value wrong. Do not build
an unattended recorder scraper or infer prices from tax without a documented
county rule and quality flag.

### ATTOM: secondary commercial recorded-sale source

- Signup: [ATTOM Developer account](https://api.developer.attomdata.com/signup)
- Documentation: [ATTOM API docs](https://api.developer.attomdata.com/docs)
- Trial: ATTOM advertises a 30-day trial; production terms and pricing require
  confirmation.
- Authentication: `apikey: ${ATTOM_API_KEY}`
- Relevant endpoint/package: `/saleshistory/basichistory` or the current
  Property V2 transaction resources.
- Useful fields: APN, transaction and recording dates, document number,
  `saleAmt`, actual/estimated sale code, disclosure type, document/transaction
  type, source publish date, and last-modified date.
- Cadence: ATTOM documents assessor and recorder updates on weekdays.

ATTOM's trial/legal terms can restrict retention after termination. Do not
persist or redistribute ATTOM records until the selected production agreement
explicitly permits RealtyKit's storage and display behavior.

## Normalized data contract

Keep listings and closed transactions in separate tables and expose provenance
on every row.

```text
property_listings
  provider, provider_listing_id, property_id, county_fips, parcel_id,
  address, city, state, postal_code, latitude, longitude, property_type,
  beds, baths, sqft, list_price, original_list_price, status,
  listed_at, removed_at, days_on_market, source_updated_at, fetched_at,
  source_url, display_license

sale_events
  provider, provider_event_id, property_id, county_fips, parcel_id,
  document_number, address, city, state, postal_code, latitude, longitude,
  property_type, sale_price, price_kind, sale_date, recorded_at,
  transfer_type, arms_length, source_published_at, source_updated_at,
  fetched_at, source_url, quality_flags, display_license
```

`price_kind` must be one of `recorded_consideration`, `mls_close_price`,
`vendor_recorded_sale`, `estimated_sale`, or `unknown`. Never present assessed
value, AVM, documentary-transfer-tax inference, or list price as a sold price.

Avoid storing owner, buyer, seller, agent email, or agent phone fields unless a
later feature explicitly needs them and the applicable license permits it.

### Deduplication and quality

Preferred identity order:

1. `(county_fips, parcel_id, document_number, recorded_at)` for official deeds;
2. `(provider, provider_event_id)` for MLS/vendor records;
3. normalized address plus sale date and sale price as a flagged fallback.

Attach quality flags instead of silently dropping unusual events:
`nominal_consideration`, `non_arms_length`, `family_transfer`, `foreclosure`,
`partial_interest`, `multi_parcel`, `estimated_price`, `missing_apn`, and
`duplicate_candidate`.

## Refresh design

### Development with the free RentCast allowance

Use address lookups and one city at a time. Do not schedule whole-city refreshes
on the 50-request plan. A single five-city pass for listings plus sales costs at
least 10 successful requests before pagination.

### Production with RentCast

- Active listings: refresh each target city every 12–24 hours; paginate until
  fewer than 500 rows are returned.
- Sold properties: query `saleDateRange=14` daily, providing a 14-day overlap
  for late county/recording updates; upsert by event identity.
- Cache raw responses in dated source folders and record response observation,
  source-update, and fetch timestamps separately.
- Mark a listing stale from `lastSeenDate`, not from the HTTP fetch time.
- Mark a sale event's recency from `sale_date`/`recorded_at`; a fresh download
  does not make an old transaction current.

### Production with MLSListings

- Perform an initial licensed snapshot, then query by
  `ModificationTimestamp` with a safety overlap.
- Refresh at the interval required by the data agreement; the source itself
  reports a five-minute update cadence.
- Retain tombstones/status transitions so removed, pending, and closed records
  do not remain falsely active.
- Enforce feed-specific display rules at the API boundary.

### County imports

- Store each delivered source file unchanged under
  `resources/government/YYYY-MM-DD/{county}/sales/` with SHA-256, source URL or
  order reference, publisher observation date, and fetched/received date.
- Parse through a county field map into `sale_events`; never special-case county
  column names in UI code.
- Report the county's quarterly or contracted publication cadence honestly.

## Acquisition checklist

1. Create a free [RentCast API account](https://app.rentcast.io/app/api), place
   the key only in root `.env` as `RENTCAST_API_KEY`, and test one address plus
   one small city query for both endpoints.
2. Measure five-city coverage against MLSListings public counts for a fixed
   date; do not rely solely on a nationwide coverage claim.
3. If production needs exact/complete MLS inventory, email
   `data@mlslistings.com` and apply with an MLS Participant Broker for the feed
   appropriate to the intended public, registered-user, or internal use.
4. Request the Santa Clara electronic two-year sales list. Separately ask San
   Mateo for a no-purchase sample and data dictionary before treating its fee
   product as relevant to sold prices.
5. Trial ATTOM only if RentCast sale history has material gaps; compare exact
   APN/address samples before signing a production contract.
6. Add automated source-level coverage checks: result count, missing price/APN,
   duplicate rate, newest `lastSeenDate`, newest sale/recording date, and sample
   agreement with an official county row.

## County request template

```text
Subject: Request for electronic property transfer/sales list under RTC 408.1

Please provide the current property-transfer/sales list for [county or target
cities/APN ranges] covering the preceding two years. If available, I request
CSV, fixed-width text, or another machine-readable format with APN, situs
address, transfer date, recording date/reference or document number,
consideration/indicated sale price when known, land-use/property type, and any
public transfer-quality codes.

Please also provide the data dictionary, observation/as-of date, update
cadence, fee, delivery method, recurring-delivery options, and terms governing
automated internal use and display of individual transaction facts in a public
application. Owner names are not required.
```

## Acceptance criteria before calling coverage complete

- A current listing and its list price can be retrieved by address and on the
  map for every target city.
- A known recently closed property returns a sale price, sale/close date,
  source, and price kind without being confused with its list price or AVM.
- The UI shows source observation date and license/display status.
- A source gap is displayed as unavailable, not filled with an estimate.
- Sample vendor sold prices are reconciled against official county or licensed
  MLS rows, with differences flagged.
- No API key, token, owner name, buyer/seller name, or agent contact detail is
  committed to Git.
