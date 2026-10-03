# Similar homes and full ownership costs

Research/design follow-up: October 2, 2026. This document turns the user's preferred ideas into implementable features. An interactive cost scenario was prepared separately for the conversation; production application behavior is unchanged.

## Similar homes: two entry paths

**Start with an address.** Resolve an exact property through RentCast's property-record endpoint, show the returned address/type/beds/baths/size and let the user correct missing or inaccurate attributes. Ask whether they want homes currently for sale, rentals, or recently sold comparables. Default to the subject property's area, property type and an editable size range. Never infer a subject property's characteristics from its nearest metro's averages: the current Census address flow resolves a tracked geography, not a property profile.

**Start with requirements.** Accept one or more areas, buy/rent intent, budget, beds/baths, property type and optional size. Apply strict user requirements before ranking; distinguish required criteria from preferences. Structured controls can accompany natural-language requirements, but the parsed criteria must be visible and editable before the search. Avoid protected-class inputs or demographic steering.

Show an explicit explanation per result, for example “same property type; 0.8 miles away; 120 sq ft smaller; asking price within your budget.” Explain differences without an unvalidated percentage similarity score. Show asking price separately from recorded sale price, provider timestamps, missing fields, and why a criterion could not be evaluated. Clearly distinguish available listings from sold evidence. A sold record is not an available home, and aggregate Redfin/Zillow research cannot produce address-level matches.

The existing RentCast key is configured; no credential is needed from the user. This research did not make live, billable RentCast calls. [Sale listing search](https://developers.rentcast.io/reference/sale-listings), [rental listing search](https://developers.rentcast.io/reference/rental-listings-long-term), [property records](https://developers.rentcast.io/reference/property-records) and [value/rent comparables](https://developers.rentcast.io/reference/value-estimate) provide distinct tools. Provider valuation comps may include inactive records and should not be represented as active inventory. Exact supported filter names/ranges and query limits should be validated against documentation when implementing.

### Architecture and budget constraints

- Extend `realtykit/providers/rentcast.py` with typed subject-property and criteria queries; expose a search route separate from `/api/map/listings` rather than overloading map coordinates with all requirements.
- Maintain the current hard limit of **40 attempted requests/month**, warning at 32, and usage visibility. One cache-miss address lookup plus one listing query already consumes two requests. Provider errors can consume attempts. Cache reusable query results, then rerank locally when preferences change. Do not trigger a request on every keystroke or map movement.
- The current radial query followed by bbox filtering caps a response at 500 and has no pagination. Mark potentially truncated results; implement bounded pagination with usage accounting before promising complete inventory. Do not silently expand radius or relax required criteria.
- Preserve property IDs, apartment/unit numbers, source/status/event dates and response provenance. Do not merge a building into its units or conflate listing history with executed-sale transactions.
- Initially support a single bounded area and explicit search action. Requirements across several regions need a visible request budget and a coverage statement.
- Store the key only on the backend. Add safeguards against third-party scraping of any public search service. A user entering an address should understand which external provider receives that address; avoid unnecessary precise-location logging.

## Generic home ownership calculator

Offer a standalone calculator that does not require an address, listing or provider request. It can also open with a selected home's price and verified tax/HOA facts, each with an editable source/assumption. User-provided loan quotes and actual insurance/tax estimates are preferable to universal fee percentages.

### Expense inventory

| When | Inputs to expose | Accounting treatment |
|---|---|---|
| Before/at purchase | Down payment; earnest deposit; lender origination and points; appraisal/credit fees; title/settlement/attorney; recording and applicable transfer/mortgage taxes; inspections and specialist checks; buyer-agent compensation when agreed; HOA transfer charges; loan-program upfront fees; prepaid interest/insurance/tax prorations; initial escrow; seller/lender credits | Earnest deposit is part of acquisition cash already paid. Financed fees increase the loan rather than cash paid. Down payment is invested equity, not a fee. |
| Move-in | Moving, immediate repairs, furnishings, utility deposits | Separate optional spending and refundable deposits. Retained emergency cash is savings, not expenditure. |
| Monthly | Principal/interest, mortgage insurance, property tax, homeowners and separate flood/earthquake coverage, HOA/condo dues, utilities/water/sewer/trash/internet, services, known assessments | Normalize annual bills to monthly budgeting, but do not add taxes/insurance again if starting from a mortgage payment that already includes escrow. Avoid adding services included in HOA dues twice. |
| Yearly/irregular | Annual premium/tax bills, maintenance, HVAC/roof/other replacements, special assessments, insurance deductibles and renewal changes | Separate monthly reserve savings from actual repair payments. A funded repair paid from that reserve is not a second expense. |

The [CFPB Loan Estimate](https://www.consumerfinance.gov/owning-a-home/loan-estimate/) and [Closing Disclosure](https://www.consumerfinance.gov/owning-a-home/closing-disclosure/) provide the acquisition-cost structure and reconciliation. Its [monthly payment worksheet](https://files.consumerfinance.gov/f/documents/cfpb_buying-a-house_monthly-payment_worksheet.pdf) extends the budget beyond the mortgage. Flood/earthquake premiums must be optional explicit inputs rather than assumed covered by homeowners insurance; see [CFPB disaster preparation](https://www.consumerfinance.gov/consumer-tools/disasters-and-emergencies/get-prepared-before-disaster-emergency-strikes/).

### Outputs and calculations

Provide (1) total cash/resources needed before purchase, split into acquisition, move-in and retained savings; (2) remaining cash to close after deposits/credits; (3) monthly bills plus reserve contributions; (4) annual budget; and later (5) a dated first-year payment calendar and multiyear projection separating principal/equity, expenses and savings. The annual budget is a run rate, not necessarily the first year's cash outflow: prepaids, escrow balances and purchase date change payment timing.

For a fixed-rate mortgage, compute principal and interest from loan balance, note rate and number of monthly payments. Handle zero interest as principal divided by payments, and an all-cash purchase as zero mortgage/MI. An APR is not the note rate used for amortization. Mortgage insurance is an explicit quoted input; cancellation and FHA/VA/USDA rules need separate loan-specific logic.

The conversation prototype uses grouped closing costs, manual recurring inputs, fixed rates and constant yearly bills. It includes credits and already-paid acquisition cash, and labels retained reserve separately. It is not a first-year ledger or a rent/buy break-even model. Detailed receipt reconciliation, financed closing fees, tax reassessment, amortization schedules, fee escalation and sale proceeds belong in the production calculator's next scope.

Useful later scenarios: rate changes, higher taxes/insurance, one major repair, different down payment and holding period. A rent/buy comparison must include sale costs, opportunity cost, rent/expense escalation and uncertain future value; it must not call principal payments an economic loss or claim a guaranteed break-even date.

## Practical permitted display paths

The current [RentCast API license](https://www.rentcast.io/terms-api) §1 permits storing and displaying/distributing API data, subject to the rest of its agreement and applicable upstream rights (§3.3). This supports independently designed factual search cards and analytics. §6.3 does not license content on a linked external site; a listing URL does not grant its photos/descriptions. Use factual cards with licensed/owned images or no photograph. §7 permits continued use of lawfully obtained data under surviving terms, with possible law/upstream-required deletion.

Other options are self-authored calculations and user inputs, government data with source-specific reuse permission, a written MLS/IDX/broker/vendor agreement covering intended fields and media, or an explicit publisher/portal partnership. Linking can accompany these cards only under the destination's terms; provider branding, export rights, caching and photos should each be recorded in a source-permission manifest. [Detailed linking analysis](linking-and-display-rights.md) covers Zillow/Realtor/Apartments limitations. Public availability alone does not establish reuse rights, including for official GIS sources.

Recommended first implementation: standalone calculator, then address/requirements search using the configured RentCast backend, then official hazard layers with source-specific display permissions and coverage states. These recommendations reflect feasibility and the user's preferences, not measured product demand.
