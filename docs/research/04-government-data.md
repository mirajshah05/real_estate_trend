# Government and public historical housing data

Research completed 2026-09-01 for RealtyKit. The key distinction is between
aggregate market indexes, mortgage records, and actual deed/recorder events.

## Best fits

| Source | What it adds | Cadence / access | RealtyKit posture |
|---|---|---|---|
| [FHFA House Price Index](https://www.fhfa.gov/data/hpi/datasets) | Purchase-only and expanded house-price indexes for the US, states, metros, counties, and developmental ZIP products; long historical coverage | Monthly/quarterly files; no key for downloads | Add as a separate `house_price_index` provider. Never label it median sale price. |
| [Freddie Mac PMMS](https://www.freddiemac.com/pmms/pmms_archives) | 30-year and 15-year mortgage-rate history since 1971 | Weekly direct files; no key | Prefer the direct official file as a fallback/supplement to FRED. |
| [Census New Residential Sales](https://www.census.gov/construction/nrs/data/series.html) | New-home sales, inventory, median/average prices, and price ranges | Monthly/quarterly files; downloads do not require a key | Add as `new_home_sales`; keep separate from existing-home metrics. |
| [HMDA Data Browser](https://ffiec.cfpb.gov/data-publication) | Purchase-loan originations, loan amount, property value, rate, purpose, property type, and geography | Annual public files plus public browser/API surfaces | Use for financing/origination context. `property_value` is not a deed sale price. |
| [FHFA UAD PUF](https://www.fhfa.gov/data/uad/puf) | Public appraisal sample with contract/appraised values and property characteristics | Historical zipped files; no key | Useful for validation and appraisal analysis, not current or parcel-complete sale history. |
| [US Treasury rates](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView) | Daily Treasury yields for rate-spread context | Public daily CSV/XML; no key | Optional macro overlay; not a mortgage quote. |
| [American Housing Survey](https://www.census.gov/programs-surveys/ahs/data.html) | Survey purchase price, year acquired, value, mortgage, and condition data | Biennial; public files; no key | Validation/affordability context, not transaction records. |

## Actual historical sale prices

There is no single federal, nationwide, current parcel-level deed-sale API.
Actual sale events are jurisdiction-specific assessor/recorder data. Some are
bulk downloads or Socrata APIs; for example, [NYC's rolling sales dataset](https://data.cityofnewyork.us/resource/usep-8jbt.json)
contains sale date, sale price, address, parcel identifiers, and property
fields, with the usual caveats around non-arm's-length and zero-dollar
transfers. The future schema should be a separate `sale_events` table with:

`jurisdiction`, `parcel_id`, `sale_date`, `sale_price`, `transfer_type`,
`property_type`, `source_url`, `published_at`, and `quality_flag`.

Do not merge these records with Zillow/Redfin estimates under the same metric.
Normalize recording/deed dates explicitly, exclude or flag nominal transfers,
and document jurisdiction-specific coverage.

## California, Bay Area, and San Francisco

California does not publish a single statewide parcel-sale API. The practical
official-data route is county by county. California Revenue and Taxation Code
section 408.1 requires each county assessor to maintain a public list of
property-interest transfers from the preceding two years, revise it quarterly,
and include the parcel, address, transfer/recording dates, recording reference,
and consideration when known. The public list can still require an inspection,
data request, or county fee rather than being exposed as an API. The completed
PCOR/change-of-ownership questionnaire itself is confidential and must not be
treated as a public feed. See the [Board of Equalization's section 408.1
summary](https://www.boe.ca.gov/proptaxes/pdf/260_0066.pdf) and [change in
ownership FAQ](https://www.boe.ca.gov/proptaxes/faqs/changeinownership.htm).

### San Francisco

The best no-key, machine-readable starting point is DataSF's [Assessor
Historical Secured Property Tax Rolls](https://data.sfgov.org/d/wv5m-vpq2).
It is a public-domain Socrata dataset available through the SODA endpoint
`https://data.sfgov.org/resource/wv5m-vpq2.json`. It includes fiscal-year
history, APN/block/lot, property location and characteristics, point geometry,
assessed land/improvement values, `current_sales_date`, `data_as_of`, and
`data_loaded_at`.

Canonical connector endpoints are:

- metadata: `https://data.sfgov.org/api/views/wv5m-vpq2`
- bulk CSV: `https://data.sfgov.org/api/v3/views/wv5m-vpq2/export.csv?accessType=DOWNLOAD`
- bulk JSON: `https://data.sfgov.org/api/v3/views/wv5m-vpq2/query.json?accessType=DOWNLOAD`
- GeoJSON: `https://data.sfgov.org/api/v3/views/wv5m-vpq2/query.geojson?accessType=DOWNLOAD`

Ordinary access does not require a key. A Socrata application token is optional
for higher request limits; the connector should prefer the annual bulk file and
use SODA queries only for small diagnostics.

Important limitation: it does **not** include the actual consideration/sale
price and is updated annually after the secured roll closes. Assessed value is
not safe to relabel as sale price. This source is suitable for the historical
parcel map, property characteristics, last-transfer date, and assessment-value
changes, but it cannot satisfy a seven-day transaction SLA.

For fresher official assessment data, San Francisco publishes an [Assessor data
request form](https://media.api.sf.gov/documents/Data_Request_Form.pdf). The
form currently lists a $350 fee for an up-to-the-minute secured assessment roll
and an expected processing period of up to 20 days. This is a file-delivery
workflow, not an API, and still does not promise public sale consideration.

The Recorder's document index can be searched online, but San Francisco states
that the online search returns only partial document information; actual
documents or copies require an office/mail workflow. Recorded documents and
transfer-tax declarations may support individual verification, but the current
public interface is not an appropriate unattended bulk connector. See the
[SF property-transfer fact sheet](https://media.api.sf.gov/documents/ASR_Factsheet_PropertyTransfer_English_2025.pdf).

For exact San Francisco prices, request the section 408.1 transfer list from
`assessor@sfgov.org` in CSV or another electronic format and ask whether a
recurring delivery is available. The request should explicitly ask for APN,
property address, transfer date, recording date/reference, consideration where
known, property/use code, and a field that distinguishes reassessable or
non-arm's-length transfers when legally disclosable.

### Marin and the rest of the Bay Area

Marin County's official [Real Estate Sales Data](https://arcc.marincounty.gov/property-information/real-estate-sales-data)
page exposes month/year reports after accepting its disclaimer. Marin's 2025
[county fee study](https://assets.marincounty.gov/arcc-prod/public/2025-06/User%20Fees%20Study%20Final%20Report_05292025.pdf)
also describes a property-transfer list prepared every two weeks with APN,
situs, deed number, recordation date, indicated sale price, use/class fields,
and property characteristics. This is the strongest price-bearing government
candidate identified in the Bay Area, but the county should confirm the file
format, fee/subscription terms, redistribution rights, and supported delivery
method before an automated connector is enabled. Marin's interactive assessor
portal also places restrictions on commercial use without written permission,
so its terms must not be assumed to authorize bulk ingestion or redistribution.

Alameda, Contra Costa, Santa Clara, San Mateo, and the other Bay Area counties
all have the same section 408.1 transfer-list obligation, but no common bulk API
was identified. Their first integration should therefore use the same
normalized county adapter with a secure CSV/file-import transport; switch a
county to HTTP/API/SFTP only when that county confirms an official automated
delivery option. A refresh must report the county's publication cadence rather
than implying that a successful download made the observations less than seven
days old.

Useful non-price geography sources include San Mateo County's [daily parcel GIS
downloads](https://www.smcgov.org/tsd/gis-data-download) and [active-parcel
FeatureServer](https://gis.smcgov.org/maps/rest/services/ACRE/ACTIVE_PARCELS/FeatureServer).
Alameda's Clerk-Recorder, Santa Clara's Assessor/Clerk-Recorder, Contra Costa's
Assessor, and other county record systems should be treated as request/search
workflows until the county documents a bulk interface and its terms. Recorder
document pages must not be scraped as a substitute for an approved feed.

### Implemented free South Bay geography connector

Palo Alto, Santa Clara, Mountain View, Sunnyvale, and San Jose are in **Santa
Clara County**, not San Mateo County. RealtyKit now refreshes their official
city polygons from Santa Clara County's [city-limits FeatureServer](https://services2.arcgis.com/tcv2cMrq63AgvbHF/ArcGIS/rest/services/PlanningOfficeDataService2/FeatureServer/2)
and their address-derived parcel counts from the county's [public-parcel
FeatureServer](https://services2.arcgis.com/tcv2cMrq63AgvbHF/arcgis/rest/services/Parcels_Public_View/FeatureServer/0).
The parcel layer includes APN, situs address, acreage, recorded square footage,
year built, and document number fields. It does not expose a reliable sale
consideration field, so the UI labels the overlay as parcel coverage rather
than sold-home pricing.

San Mateo's free GIS service is still refreshed as adjacent-source metadata.
It cannot be used to fill these five cities because county parcel boundaries
stop at the county line. Each run writes date-scoped inputs and a SHA-256
provenance manifest under `resources/government/YYYY-MM-DD/`; full parcel
polygons are not bulk-downloaded because the five target cities contain more
than 350,000 address-matched parcel records. A future close-up parcel view
should use bounded ArcGIS queries and cache those responses in the same dated
snapshot.

### Connector design

Implement two layers instead of encoding county-specific fields in analytics:

1. `CaliforniaCountySalesProvider` handles checkpoints, downloads or delivered
   files, raw snapshots, source metadata, and jurisdiction-specific parsing.
2. A normalized `sale_events` store supplies API/map/trend queries with
   `county_fips`, `parcel_id`, `document_number`, `sale_date`, `recorded_at`,
   `sale_price`, `price_kind`, `transfer_type`, `property_type`, `address`,
   `latitude`, `longitude`, `published_at`, `fetched_at`, `source_url`, and
   `quality_flag`.

San Francisco roll rows belong in a separate parcel/assessment table with
`sale_price = NULL` and `sale_price_status = not_published`; they should not be
inserted into `sale_events` merely because `current_sales_date` is present.

Use `(county_fips, parcel_id, document_number, recorded_at)` as the natural
deduplication key, retain the raw source row, and flag rather than silently
discard zero/nominal consideration, gifts, family transfers, partial-interest
transfers, foreclosures, multi-parcel transactions, and non-residential
property. DataSF parcel geometry can locate San Francisco records without
geocoding every address. Other counties should join sale rows to the county's
official parcel layer by APN when available.

The refresh result must keep three separate timestamps: the transaction or
observation date, the government publisher's `published_at`/`data_as_of`, and
RealtyKit's `fetched_at`. `--force` may refetch the source, but only a newer
publisher observation can clear transaction staleness.

## Search and geography

The app now uses the [Census Geocoder](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html)
for full US address lookup. It is a public REST service and does not require a
key. The result centers the map at the matched address and shows metrics for
the nearest tracked metro. ZIP centroids come from Census ZCTA geography.

## Recommended next provider work

1. Add FHFA HPI and direct Freddie Mac PMMS first; both improve historical
   context without introducing credentials.
2. Add Census New Residential Sales as a distinct new-construction series.
3. Add HMDA for loan/origination context, preserving the distinction between
   property value and transaction sale price.
4. Build the San Francisco DataSF parcel-history adapter and generic California
   transfer-list CSV importer first. Add Marin as the first exact-price county
   after its automated delivery and usage terms are confirmed, then expand to
   the remaining Bay Area counties.
