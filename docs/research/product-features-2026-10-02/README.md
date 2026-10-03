# RealtyKit product and data opportunity research

Research date: October 2, 2026, America/Los_Angeles. Three parallel research agents investigated competitors/repositories, vendor datasets, and public transaction records; the coordinating agent inspected the app/local data and provider linking/display terms. Follow-up research downloaded and analyzed NJ state sale files and federal historical indexes, verified a Redfin national download, and designed similar-home, ownership-cost and hazard-map features. Findings prioritize official publishers, government documentation, actual service metadata, and repository licenses. No product code, provider subscriptions, or production integrations were changed.

## Decision

Build toward an evidence-based housing decision workspace: saved home/area comparisons, explicit affordability scenarios, negotiation context, and explainable recent-sale comparables. RealtyKit already has geographic trends, a rent estimator, maps, outliers and correlations. More value comes from connecting those capabilities to a user's decision and improving transaction coverage than from duplicating another portal's search page.

The fastest first slice uses existing market data and user inputs: saved comparisons plus all-in ownership/rent-versus-buy scenarios. The strongest new data-backed slice is a government-record sold-comp explorer, initially NYC/New Jersey and a bounded Sonoma experiment. South Bay coverage still needs licensed property data or a documented county transfer product. This is a product recommendation, not a claim of market demand validation.

## Research notes

- [Competitors, feature opportunities, and five GitHub repositories](competitors-and-repositories.md)
- [Compass, Redfin and Zillow offline dataset options](vendor-datasets.md)
- [New York, New Jersey and all nine Bay Area counties](government-records.md)
- [Outbound links, third-party content and licensed display](linking-and-display-rights.md)
- [Similar-home search and generic ownership-cost calculator](ownership-cost-and-similar-home-features.md)
- [ZTRAX eligibility, verified Redfin download, and RentCast endpoints](ztrax-access-and-redfin-downloads.md)
- [NJ recent sale-file analysis and 2008-crisis index comparison](nj-recent-and-crisis-analysis.md)
- [Official hazard layers and map integration design](hazard-map-features.md)

## Follow-up decisions and completed evidence

The existing RentCast key is configured. Start similar-home search with two entry paths: an address whose property attributes are confirmed/corrected by the user, or explicit buy/rent requirements. Keep active listings separate from sold evidence and explain matches. Preserve the app's 40-attempt monthly cap and expose truncation/coverage rather than promising exhaustive results. No live RentCast call was made during research.

Build the ownership calculator as a generic input-driven tool, with optional listing prefill. Show acquisition cash, remaining cash to close, move-in spending, retained reserves, monthly bills and yearly run rate. A first-year ledger must reconcile prepaids/escrow rather than summing acquisition prepaids and twelve identical monthly allocations. The conversation includes an interactive fixed-rate prototype; detailed categories and accounting requirements are in the feature note.

Add official hazard layers incrementally to the existing Leaflet map: CGS earthquake zones and coverage, EPA Superfund, NJ contaminated-site points and groundwater polygons first; FEMA after sample-query validation. NY remediation boundary downloads explicitly prohibit secondary distribution, so link to official records until the intended display/cache route is cleared. A mapped zone or nearby site is evidence, not a prediction of damage or exposure.

ZTRAX's published conditions exclude commercial/product research and unaffiliated independent research. It is not an eligible RealtyKit feed. A separate qualified institutional noncommercial project may apply. Redfin research is downloadable: the actual national gzip parsed to 1,903 aggregate rows, January 2012–May 2026. The newer filtered CSV UI exists but a completed export was not verified; its adapter also needs property-type/seasonal-adjustment dimensions fixed before reliable comparisons.

NJ acquisition is now completed: four official ZIPs plus layouts/guidelines and FHFA indexes are stored locally under ignored `data/research/nj-2026-10-02/`. The reproducible script is `scripts/research/nj_recent_and_crisis.py`; outputs omit owner information. Usable class-2 residential medians were $520,000 (July 2024–June 2025 recording window) and $542,000 (July 2025–June 2026), +4.23%, with screened counts down 2.61%. These are changing sale samples, not repeat-sales appreciation. FHFA's separate NJ purchase-only seasonally adjusted index rose 4.59% over one year and 12.48% over two years to 2026Q2; its precrisis peak-to-trough decline was 23.02%, 2006Q2–2012Q1, with nominal recovery in 2020Q3. No 2008 individual-sale file was obtained. See the analysis for screening sensitivity, publication revisions and source provenance.

## What the app can support today

Reviewed README, provider implementations, property/rental panels, rental methodology, sale persistence, government snapshot manifest, and a read-only query of the existing SQLite database. Counts are the local cache on the research date, not publisher completeness or currently fresh coverage.

| Available locally | Observation |
|---|---|
| Market facts | 1,083,055 observations total; Zillow has 1,082,190 across 932 distinct geographies, with latest stored observation August 15, 2026 |
| Redfin | 865 observations for one national geography, January 2012–May 2026; current adapter uses one legacy national file |
| Geography | 34,728 stored geographic records; these do not all have market measurements |
| Property-level records | Zero rows in both `listings` and `sale_events`; implementing an endpoint does not establish populated coverage |
| Rental evidence | 32 stored observations; existing comparable estimator has no held-out accuracy claim |
| Government context | Five South Bay areas; the dated GIS snapshot supplies boundaries/parcel references, not sale consideration |
| Provider constraint | Hard application cap of 40 attempted RentCast requests per calendar month; data collection must be bounded and deliberate |

The stored source ledger includes historical statuses. For example, a stored `live` label on an August stock observation is not evidence that it is live on October 2. No full ingest was run during this task.

## 1. Competitor capabilities and source patterns

Zillow and Redfin combine licensed MLS data, public records and proprietary models; Compass adds collaborative Collections and private inventory. Realtor.com has both MLS consumer listings and a separate downloadable aggregate research library. Homes.com adds editorial neighborhood/building context and CoStar research. Apartments.com receives rental content through managers and property-management integrations. RentCast documents county/deed/assessor records and public listing feeds; its listing product is not a direct MLS feed. PropStream distinguishes MLS and public-record comps, while DealCheck focuses on scenario calculations. Sources and exact provenance limits are in the [competitor table](competitors-and-repositories.md).

These are different inputs and measures: modeled home value, asking price, executed-sale consideration, tax assessment, recorded transfer, asking rent and occupied gross rent must remain identifiable. A county transfer alone usually cannot reconstruct original asking price, price cuts, listing photos or MLS days on market.

## 2. Offline/downloadable vendor data

| Publisher | Downloadable path | Suitable use | Main limitation |
|---|---|---|---|
| Zillow Research | Public aggregate CSV series including ZHVI, ZORI, inventory and other market metrics | Dated local market history and charts | Aggregate series are not an address-level listing feed; use/redistribution must follow applicable terms and attribution |
| Zillow/Bridge Economic Data API | Documented approval/token-based API for aggregate research indicators | Programmatic aggregate access | Written app permission and product-specific cache/display conditions; not an anonymous offline feed |
| Zillow ZTRAX | ICPSR-managed property-level transaction/assessment dataset, restored in 2026 | Eligible academic/nonprofit/government research under its agreement | Restricted eligibility and uses; do not treat as a general commercial offline feed |
| Redfin Data Center | Public research downloads; new 2026 portal offers additional local negotiation and financing metrics | Aggregate sale/liquidity context | Portal exports need schema/methodology review; a stable current automated export endpoint remains to be established |
| Compass | Market reports were found; no public self-service bulk listing/transaction feed was verified | Product inspiration and reading | Written license/authorized MLS route is required for a dependable in-app listing-data integration |

Redfin's May 2026 release adds downloadable price-drop, cancellation, relisting and sale-to-original-list metrics and changes seasonal-adjustment defaults. Existing RealtyKit code only ingests the legacy national object. [Official release](https://www.redfin.com/news/new-redfin-data-center/).

ZTRAX access was restored through ICPSR after the earlier distribution shutdown; relying on old reports that it is permanently unavailable would be incorrect. [ICPSR announcement](https://www.icpsr.umich.edu/sites/icpsr/news/7-things-to-know-about-the-ztrax-database-at-icpsr), [Zillow ZTRAX](https://www.zillow.com/research/ztrax/).

Zillow's current economic API is documented through [Bridge](https://bridgedataoutput.com/docs/platform/Introduction). Its [API-specific terms](https://bridgedataoutput.com/zillowterms) impose written app/competitive-product permission, end-user caching/download restrictions, attribution and termination deletion. Those terms should not be conflated with research CSV terms.

The [vendor note](vendor-datasets.md) records small metadata/header probes, latest observations, direct examples and unresolved rights. Do not treat a successful download today as an observation from today, or a weekly measurement interval as proof the publisher updates its file weekly.

## 3. Official recent-sales records

| Region | Evidence-backed path | Recommended scope |
|---|---|---|
| New York outside NYC | SalesWeb has ten years of RP-5217 transfer data and compressed CSV downloads, with weekly updates and potential weeks/months of lag | Statewide history with property-class and transaction-condition filtering; co-op transfers are excluded |
| New York City | DOF rolling sales covers all five boroughs, with borough spreadsheets and a citywide Open Data table; annual history begins 2003 | Best first machine-readable public-sale pilot; distinguish residential units, mixed/commercial transactions, nominal transfers and multi-property deals |
| New Jersey | Treasury publishes SR1A sales downloads and file layouts; MOD-IV is a separate assessment product | Second pilot after fixed-width/layout parsing, municipal/block/lot joins, and non-usable-sale filtering |
| California Bay Area | No statewide equivalent sale-price download was verified; access is county-specific | Sonoma's sale-bearing GIS metadata is the strongest free Bay Area experiment found; other counties require separate validation or licensed access |

Sources: [NY SalesWeb](https://www.tax.ny.gov/research/property/assess/sales/salesweb.htm), [NYC DOF rolling sales](https://www.nyc.gov/site/finance/property/property-rolling-sales-data.page), [NYC official dataset catalog](https://catalog.data.gov/dataset/nyc-citywide-rolling-calendar-sales), [NJ Treasury statistics/downloads](https://www.nj.gov/treasury/taxation/lpt/statdata.shtml). See the [government note](government-records.md) for county-level access, fields, fees, service URLs and gaps.

Verification is uneven: NYC's catalog/metadata and published borough files were inspected; NJ's current files were subsequently downloaded and parsed in the follow-up analysis, but were not imported into app tables; NY SalesWeb's offering is documented in official indexed content but its live application/download was not verified; Sonoma's schema was verified but live sample rows, price derivation and actual sale latency were not. These are acquisition candidates, not completed product integrations.

The new findings also correct earlier assumptions: Marin's transfer-list price is tax-derived and can differ from purchase consideration, and Santa Clara Recorder subscriptions expressly lack real-estate sale-price/address data. Napa advertises a monthly sales list for $131/year and San Mateo lists sales history at $305, but neither product's fields/transport were validated. [Marin fee study](https://assets.marincounty.gov/arcc-prod/public/2025-06/User%20Fees%20Study%20Final%20Report_05292025.pdf), [Santa Clara subscription description](https://clerkrecorder.santaclaracounty.gov/official-records/subscribe-data-sales-reports), [Napa fee schedule](https://www.countyofnapa.org/2077/Assessor-Fee-Schedule), [San Mateo fees](https://smcacre.gov/assessor/assessment-data-fees).

Do not label every transfer as an arms-length home closing. Preserve the source's own event dates, price meaning and validation flags. Recording and publication delays preclude promising complete last-seven-day closings. Public access also does not settle every public-redistribution, privacy or media right.

## 4. Can we link or showcase a portal inside RealtyKit?

Yes, an integration is possible, but there is no blanket rule that linking grants rights to showcase the original site's content. The practical choices are a permitted plain click-through, independent cards backed by official/licensed facts, or explicitly licensed listing/media display.

- Zillow's current terms impose an operator qualification on third-party links; merely being housing-related is insufficient.
- Realtor.com requires permission for deep links and prior written notice plus attribution for its homepage exception; it prohibits framing under those linking conditions.
- Apartments.com explicitly allows unchanged canonical-page links, but also has a non-competitor condition that needs resolution for RealtyKit's intended public product.
- No blanket incoming-link prohibition was located in the reviewed Redfin/Compass terms; that is not affirmative permission to copy their content, scrape URL discovery, or embed their sites.
- RentCast's current API grant expressly permits storage and third-party display subject to surviving/third-party conditions. This is the clearest fit with the existing adapter. MLS/IDX or ListHub is another contracted path, each with product-specific conditions.

Sources and the proposed integration design are in [linking and display rights](linking-and-display-rights.md). A lawyer/provider should resolve ambiguous product permissions before public launch; this research does not certify legal clearance. No contact or permission request was sent.

## Feature roadmap

| Order | Feature | Concrete user value | Inputs / effort judgment |
|---|---|---|---|
| 1 | Saved property/area comparison workspace | Keep three alternatives, notes and dated evidence together; compare and export research | Existing cached metrics + user inputs; small-to-medium scope |
| 1 | All-in affordability and buy-versus-rent scenarios | Compare monthly cost, upfront cash, holding-period break-even and rate sensitivity | Current rate/price/rent context + explicit tax, insurance, HOA, maintenance and transaction-cost assumptions; medium |
| 1 | Address/requirements similar-home search | Find available homes or separately inspect sold evidence; explain each match | Configured RentCast key + bounded queries, editable attributes, request accounting and cache; medium |
| 2 | Official hazard map overlays | Inspect earthquake zones, flood designations and cleanup/water context around homes | Source-specific government GIS adapters, coverage, dates and reuse permission; medium-to-large |
| 2 | Negotiation/liquidity context | Interpret price cuts, sale-to-list ratios, relistings and cancellations alongside inventory/DOM | Authorized Redfin/Realtor research exports, geography and definition alignment; medium |
| 2 | Official sold-comp explorer | Filter nearby residential sales, explain exclusions, and inspect source disagreements | NYC then NJ; Sonoma experiment; identity matching, date/price semantics and geography; medium-to-large |
| 3 | Property dossier | Connect parcel, permitted work, zoning and hazard-map evidence to a subject home | Jurisdiction-specific official sources; validate beyond this sale-data research; large across regions |
| 3 | Fee-adjusted rental/investor worksheet | Incorporate concessions, recurring fees, vacancy and expenses into a transparent scenario | User/licensed inputs + existing rent evidence; HUD/ACS are benchmark context, not signed-lease records; medium |

Effort labels are preliminary judgments, not delivery estimates. Commute/access exploration is another candidate, but requires separate routing/transit source validation. A generalized desirability score would obscure the evidence and introduce issues the current product need not create.

## Proposed first implementation sequence

1. Add a local saved comparison workspace and scenario calculator. Build on existing `/api/trends`, research and rental-estimate capabilities. Preserve source dates and make all financial assumptions editable.
2. Add a source-permission manifest and aggregate metric definitions before expanding public displays. Separate observation cadence, publication cadence and publication delay in freshness handling.
3. Pilot NYC DOF import with its current table plus annual/borough-file history. Add a government-specific event store or extend the present sale schema: it currently requires coordinates and lacks recording date, price basis, transfer flags and document provenance. Never geocode missing locations to fictitious coordinates.
4. Add NJ after verifying the exact data layout and deduplication key. Prototype a small Sonoma sample only after confirming field semantics, completeness, available history and terms. Do not imply it solves San Jose/Palo Alto coverage.
5. Integrate current Redfin research exports via a documented endpoint or supported manual CSV import. Keep raw publication versions because seasonal adjustment and late records can revise history.

A successful transaction pilot should measure residential-record count, invalid/zero prices, usable-sale flags, location-match rate, duplicate/multi-parcel events, recording/publication lag and sample agreement with original official records. NJ's follow-up analysis executes a research parser and aggregate comparisons with hashes and quality checks; geocoding and production app imports remain unbuilt.

## Repository reuse decisions

Five repositories were inspected. OpenAddresses is useful for official endpoint discovery and address/parcel mapping; its software license does not replace upstream dataset terms. OSMnx is useful for a later access/commute prototype, with MIT code and separate OSM ODbL/service obligations. RESO tools reference a custom EULA and are relevant only to licensed MLS access. censusdis uses Hippocratic 3.0, so a small independent Census API adapter is likely simpler for this app. HomeHarvest is a Realtor.com scraper whose MIT license does not license the extracted content; it is not the recommended feed. Actual links/licenses are in the [repository table](competitors-and-repositories.md).

## Open decisions

- Local personal research versus a publicly hosted/commercial application determines the final rights review and architecture; this report assesses both without assuming public launch is already authorized.
- Pick the first transaction geography: NYC is easiest technically; New Jersey offers strong statewide value; Sonoma is useful for Bay Area experimentation but does not cover the app's existing South Bay focus.
- Resolve provider-specific public-display, automated download, raw-export and media permissions before making a public production integration. Marketing claims of availability are not contractual grants.
- Validate demand with users: these feature priorities arise from competitor capability and engineering/data feasibility, not interviews or usage evidence.
