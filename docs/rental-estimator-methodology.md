# Rental estimator methodology and evidence

Reviewed against public first-party disclosures on September 7, 2026.

## Scope and terminology

RealtyKit's `comparable_adjustment_v1` produces a property-level estimate of monthly asking
rent from user-imported rental observations. It is a deterministic comparable analysis. It is
not an appraisal, a trained automated valuation model, a forecast, a measure of contract rent
paid by existing tenants, or a market index.

Those distinctions matter because Zillow and Redfin publish products with different units of
analysis:

- A **property-level rent estimate** answers what one home might currently be advertised for.
- An **asking-rent market statistic** summarizes listings available to new renters during a
  period.
- A **quality-controlled market index** estimates how asking rents change over time while
  reducing changes caused by which homes happen to be listed.

## What Zillow publicly discloses

### Rent Zestimate: property-level estimate

Zillow describes the Rent Zestimate as a proprietary estimate of monthly rent for a specific
property and a starting point, not a final price. Its disclosed inputs include public property
data, similar local properties listed for rent, bedrooms, bathrooms, square footage, amenities,
and owner-updated home facts. Zillow also warns that special features, location, market
conditions, negotiation, incentives, and lease length can cause actual asking or agreed rent to
differ. [Zillow: What is a Rent Zestimate?](https://www.zillow.com/rent/what-is-a-rent-zestimate/)

Zillow publishes a point estimate with a Rent Range. It says a wider range represents less data
or more volatility, while more local listings and more complete attributes generally improve
the estimate. Zillow does not disclose its current proprietary formula, coefficients, model
architecture, or a current Rent Zestimate calibration table on that page. The appropriate
lesson for RealtyKit is therefore about inputs and uncertainty behavior, not a formula to copy.
[Zillow Rental Manager: What Is the Rent Zestimate?](https://www.zillow.com/rentals-network/what-is-the-rent-zestimate/)

### ZORI: market index, not a property estimate

The Zillow Observed Rent Index (ZORI) is a regional time series. Zillow's methodology calculates
rent changes for the same units when they are repeatedly listed, aggregates the repeat-rent
pairs, and weights under- or over-represented building-age and structure categories using U.S.
Census data. This addresses listing-composition changes that can make a raw monthly median or
average move even when like-for-like rents do not. The published index is smoothed and subjected
to quality-control checks. [Zillow Research: ZORI methodology](https://www.zillow.com/research/methodology-zori-repeat-rent-27092/)

Zillow's current research data catalog calls ZORI a smoothed, rental-stock-weighted repeat-rent
measure of typical observed market-rate rent. It dollar-denominates the index using the weighted
mean of listed rents between the 35th and 65th percentiles and publishes all-home,
single-family, and multifamily series. [Zillow Research: Housing Data](https://www.zillow.com/research/data/)

ZORI must not be described as an estimate for an individual property. Conversely, a collection
of RealtyKit property estimates must not be labeled ZORI: RealtyKit does not currently implement
repeat-rent pairing, Census rental-stock weights, Zillow's smoothing, or its publication-quality
checks.

## What Redfin publicly discloses

### Redfin Rental Estimate: property-level estimate

Redfin says its Rental Estimate is a fair-market-rental-value estimate for an individual home.
Its current public explanation says it uses up-to-date rental data and similar properties that
are currently listed or were recently taken off market. Redfin identifies unique condition,
upgrades, and location as possible reasons the estimate can differ from fair market rent and
says the result is informational, not a substitute for an in-person property manager or
landlord. The page does not publish a formula, feature weights, confidence interval method,
accuracy statistics, or validation protocol. [Redfin: Rental Estimate](https://www.redfin.com/rental-estimate)

No reviewed first-party source says the property-level Redfin Rental Estimate is ZORI, a Zillow
Rent Zestimate, or the Redfin Rental Tracker median. RealtyKit should not infer those
relationships from the companies' listing partnership.

### Rental listings and Rental Tracker: partner disclosures and market statistic

Redfin's renter FAQ says rental listings on Redfin come from Redfin Rental Tools, Zillow rentals,
and selected MLSs. [Redfin Customer Service: Finding Rentals on Redfin FAQ](https://support.redfin.com/hc/en-us/articles/4517160657563-Finding-Rentals-on-Redfin-FAQ)

For its current Rental Tracker, Redfin discloses a narrower population: newly listed units in
apartment buildings with at least 25 units. It reports median asking rent over rolling
three-month periods and explicitly says this is the cost faced by new renters, not the median
rent paid by all renters. Redfin also discloses that Zillow became its exclusive provider of
multifamily rental listings in this category in 2025. [Redfin: Rental Data Methodology](https://www.redfin.com/news/redfin-rental-data-methodology/)

This tracker is a market statistic with a defined listing population, not a property-level
estimate. It is also not directly comparable to RealtyKit's uploaded observations unless an
import has the same building-size, listing-status, geography, and rolling-window definition.

## Comparison with `comparable_adjustment_v1`

| Dimension | Public Zillow/Redfin principle | RealtyKit implementation | Important difference |
|---|---|---|---|
| Unit of analysis | Rent Zestimate and Redfin Rental Estimate are property-level | One subject property | Aligned in purpose only; no model parity |
| Local evidence | Both disclose similar/local rental listings; Redfin emphasizes current or recently removed listings | Prefers same-city comparables, ranks neighborhood and ZIP matches, and downweights older observations | Neighborhoods are text labels, not measured distance; observations may be up to three years old |
| Home facts | Zillow names beds, baths, square footage and amenities; Redfin warns about condition, upgrades and location | Uses beds, baths, property type, square footage, year built and recorded amenities | Condition, renovations, exact micro-location and many lease-specific facts are absent |
| Estimate mechanics | Current formulas and coefficients are proprietary or undisclosed | Applies explicit, bounded heuristic adjustments and a weighted median | RealtyKit percentages are engineering priors, not learned effects and not vendor formulas |
| Robustness | Zillow describes data-quality controls for ZORI; property estimate details are undisclosed | Drops invalid/stale rows and trims extreme adjusted rents with a median-absolute-deviation rule | This is not Zillow's quality-control system |
| Uncertainty | Zillow says range width grows with sparse data or volatility | Uses weighted 20th/80th comparable quantiles plus a minimum width driven by sample count and evidence confidence | The range has not been calibrated to a stated coverage probability |
| Evidence quality | Zillow says local listing volume and attribute completeness affect accuracy | Confidence combines count, similarity, target/comparable attribute coverage and recency; one- and two-comp results are capped | The score is a data-quality indicator, not probability or expected error |
| Explainability | Public vendor pages show limited methodology detail | Returns ranked comparables, adjusted rents and factor-level dollar impacts | Dollar impacts inherit the unvalidated heuristic coefficients |
| Market trend | Zillow identifies changing market conditions; ZORI measures regional change | Recency affects weights only | No explicit market-time adjustment or seasonal model exists |
| Validation | Current reviewed vendor pages do not provide enough property-level detail for replication | No held-out performance statistics yet | RealtyKit must not claim accuracy, parity, or a calibrated interval |

## Current RealtyKit calculation

The implementation is intentionally small and inspectable:

1. Reject observations with missing/nonpositive rent, invalid type or bedrooms, future dates, or
   dates more than roughly three years before the requested `as_of` date.
2. Prefer same-city observations when at least three exist. Otherwise, allow other supported Bay
   Area cities as low-scoring backfill.
3. Rank candidates using city, neighborhood, ZIP, bedrooms, bathrooms, property type, square
   footage, year built, amenities, and recency.
4. Apply bounded heuristic adjustments. Current engineering priors are 11% per bedroom, 4.5%
   per bathroom, type factors of 1.00/1.10/1.20 for apartment/townhouse/single-family, damped
   square-foot scaling, a small age adjustment, and 1.5% per net recorded amenity difference.
   The combined adjustment is capped to 0.65-1.55 of the observed rent.
5. Downweight older records, trim extreme adjusted rents when at least five candidates exist,
   and take a weighted median of at most eight comparables.
6. Form the range from weighted 20th and 80th percentiles. Enforce a wider minimum band for
   small samples and for lower confidence. This is a conservative display range, not a formal
   prediction interval.
7. Compute confidence from comparable count, average similarity, target and comparable
   attribute coverage, and recency. Cap one-comparable confidence at 0.45 and two-comparable
   confidence at 0.55.

Location and recency are selection/weighting factors, so their displayed dollar impact is zero;
zero does not mean they have no effect. All other displayed impacts are averages of the
heuristic adjustments applied to selected comparables.

## Limitations and prohibited claims

- Imported `monthly_rent` is treated as asking rent. It may not be the signed lease rent and may
  exclude concessions, fees, utilities, parking or bundled services.
- `listing_status` must not be presented as incumbent-tenant contract rent unless the source
  actually defines it that way.
- Sparse neighborhood data can cause cross-city backfill. A point estimate from one or two
  comparables remains `low_data`, regardless of apparent similarity.
- The model does not observe condition, renovation quality, view, floor, exact transit access,
  furnished status, lease duration, pets, utilities, concessions, or negotiation.
- Neighborhood names can be inconsistent and are not a substitute for coordinates or a verified
  geographic boundary.
- The heuristic coefficients are not causal effects and have not been estimated from RealtyKit's
  data.
- The confidence score is not an accuracy percentage. The range has no guaranteed coverage.
- Do not call the result a Rent Zestimate, Redfin Rental Estimate, ZORI, appraisal, fair-rent
  determination, or vendor-equivalent estimate.

## Validation and improvement plan

Before upgrading the method or making accuracy statements:

1. Preserve stable property identity and repeated listing events so time-safe validation and
   repeat-rent analysis are possible.
2. Define every source's rent concept, listing status, concessions, property type, building size,
   and deduplication rules.
3. Add coordinates or verified neighborhood/ZIP boundaries and measure geographic distance.
4. Backtest chronologically: select a historical cutoff, use only facts known at that cutoff,
   and compare estimates with later observed asking rents for held-out properties.
5. Report median absolute error, median absolute percentage error, performance by city/property
   type/bedroom count, sample sizes, and range coverage. Avoid aggregate metrics that hide weak
   segments.
6. Learn or validate adjustment effects from sufficient local data rather than changing fixed
   percentages by intuition. Version every method change.
7. Consider a separately licensed regional market index only as a transparent time adjustment;
   do not relabel a market index as a property estimate.
8. Suppress estimates when a segment fails documented evidence or backtest thresholds rather
   than widening coverage through weak comparables.

## Primary sources reviewed

- [Zillow: What is a Rent Zestimate?](https://www.zillow.com/rent/what-is-a-rent-zestimate/)
- [Zillow Rental Manager: What Is the Rent Zestimate?](https://www.zillow.com/rentals-network/what-is-the-rent-zestimate/)
- [Zillow Research: Methodology — Zillow Observed Rent Index](https://www.zillow.com/research/methodology-zori-repeat-rent-27092/)
- [Zillow Research: Housing Data](https://www.zillow.com/research/data/)
- [Redfin: Rental Estimate](https://www.redfin.com/rental-estimate)
- [Redfin: Rental Data Methodology](https://www.redfin.com/news/redfin-rental-data-methodology/)
- [Redfin Customer Service: Finding Rentals on Redfin FAQ](https://support.redfin.com/hc/en-us/articles/4517160657563-Finding-Rentals-on-Redfin-FAQ)

All links are first-party pages. The comparison intentionally excludes third-party summaries,
reverse engineering, vendor trademarks as product claims, and proprietary-formula speculation.
