# ZTRAX access, Redfin downloads, and RentCast alternatives

Verified October 2, 2026. This follows the vendor dataset report and answers whether we can actually obtain ZTRAX and Redfin data. No accounts, applications, agreements, subscriptions, or paid API calls were created or submitted.

## Can RealtyKit get ZTRAX?

**The published access conditions exclude using ZTRAX for this product.** They disallow research for or with a commercial enterprise and research unaffiliated with a known educational institution, nonprofit, government entity, or policy organization. They also prohibit identification/marketing uses and require correct ZTRAX attribution when combining databases. Institutional membership alone does not cure an excluded purpose. An independent personal researcher therefore does not qualify under the published conditions. [Current study, Scope / Data Collection Notes](https://www.icpsr.umich.edu/web/ICPSR/studies/39652).

For a separate eligible noncommercial project, the study requires a confidential-data agreement, research justification, and IRB approval or exemption. V3 was released September 17, 2026 from a March 2026 extract. Its broad 1940–2026 label does not establish complete 2008 coverage: county history varies, commonly from the early 1990s or mid-2000s. Data are planned twice yearly, April/October. September metadata reports approximately 1.51 billion assessment and 1.64 billion transaction rows. Geographic subsets are recommended. Some tables are intentionally empty, including assessment sale data and owner/buyer/seller name tables. [Study description and version notes](https://www.icpsr.umich.edu/web/ICPSR/studies/39652).

ZTRAX distribution has resumed exclusively through ICPSR after the former October 2023 closure. It contains public-record transactions and assessment attributes; it excludes Zestimates, asking/contract rent, listing history, and search activity. It is restricted data, rather than an open consumer listing feed. [ICPSR April 2026 announcement](https://www.icpsr.umich.edu/sites/icpsr/news/7-things-to-know-about-the-ztrax-database-at-icpsr), [Zillow's current ZTRAX page](https://www.zillow.com/research/ztrax/).

| Applicant / intended use | Current outcome |
|---|---|
| Qualified noncommercial researcher at an ICPSR member institution | May apply; membership is not automatic approval; access is free for member users |
| Qualified researcher at a nonmember institution | May apply; affiliation and purpose requirements still apply; price requires confirmation |

The last two membership/cost distinctions are explicitly supported by [Zillow's current access description](https://www.zillow.com/research/ztrax/) and the [ICPSR announcement](https://www.icpsr.umich.edu/sites/icpsr/news/7-things-to-know-about-the-ztrax-database-at-icpsr). ICPSR's general nonmember policy mentions a typical approximately **$825 per dataset** administration fee; this is **not a verified ZTRAX quote**. Some restricted studies have separate fees shown inside the application. [Nonmember policy](https://www.icpsr.umich.edu/sites/icpsr/about/policies/non-member-data-access-policy).

## What an eligible ZTRAX application would need

ICPSR's general restricted-data process normally requests an institutional principal investigator (usually PhD/JD/MD), named staff, project justification, IRB documentation, security plan, and a use agreement signed by the investigator and institutional legal representative. Students generally need a faculty sponsor. Secure download sends encrypted files to approved secure storage; virtual enclave access keeps files on ICPSR servers and requires disclosure review for exports. The allowed access method and additional conditions depend on the study. Review generally takes 2–4 weeks after submission; annual maintenance and destruction/renewal can be required. [General restricted-data process](https://www.icpsr.umich.edu/sites/ICPSR/posts/shared/restricted-data-mgmt-access).

Authentication uses Researcher Passport or supported third-party identity. Creating an account using a personal email does not establish institutional membership. [Researcher Passport](https://www.icpsr.umich.edu/sites/icpsr/posts/shared/what-is-researcher-passport).

Public file layouts and dictionaries are downloadable documentation; they do not grant access to the records. [ICPSR announcement](https://www.icpsr.umich.edu/sites/icpsr/news/7-things-to-know-about-the-ztrax-database-at-icpsr). Zillow's official historical import example reads state folders containing headerless, pipe-delimited `ZAsmt`/`ZTrans` `.txt` tables, using a layout workbook and identifiers to join property and transaction tables. This is evidence of the historical format, **not verification of the current approved-delivery container or schema**. [Official Zillow example code](https://github.com/zillow-research/ztrax/blob/master/ExampleRcode_UsingZTRAXtoCreateHedonicDataset.R).

The full current ZTRAX-specific agreement and application fields were not retrieved: the interactive study page stayed at a security-verification screen. No verification challenge was completed. The published conditions above are sufficient to reject product use; they do not establish permission to distribute raw rows or arbitrary research outputs. If pursuing an institution-backed project, obtain its actual agreement and confirm output rules, county-by-year coverage, access method, retention period, and fees before applying.

Only if the user intends a **separate qualifying noncommercial research project** do we need further facts: sponsoring institution, principal investigator/faculty sponsor, research purpose, and IRB route. There is no useful need to ask for these merely to power RealtyKit.

## Is Redfin research downloadable?

**Yes. An actual small legacy public national dataset was downloaded and parsed successfully.** The current [official download hub](https://www.redfin.com/news/data-center/downloads/) also offers filtered CSV downloads, with geography/date/metric selection. In its Housing Market Tracker, we selected United States and August 2026; Download Data became enabled and was clicked. However, the supported browser download event timed out, so a completed current-hub file was **not verified or saved by the tool**. Browser policy also blocked inspecting the browser's internal downloads page; no workaround was attempted.

The independently supported legacy file is the exact public endpoint already used by RealtyKit's adapter:

[Redfin national tracker TSV gzip](https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/us_national_market_tracker.tsv000.gz)

| Verified download property | Result |
|---|---|
| Local downloaded artifact | `data/research/redfin-2026-10-02/redfin-national.tsv.gz` (ignored; initially downloaded to `/private/tmp/realtykit-redfin-national.tsv.gz`) |
| Compressed size | 486,979 bytes |
| SHA-256 | `4c2ea9bcf1d12e94dff3eb6ae72f9b088d1db00f380f1e2081f33d1563d07b11` |
| Parsed records / columns | 1,903 / 58 |
| Earliest period | January 1–31, 2012 |
| Latest period | May 1–31, 2026 |
| Last-update values | June 2, 2026 |
| Geography | National only (`STATE_CODE=US`, `REGION_TYPE=national`) |
| Granularity | Aggregate monthly metrics; no individual homes, addresses, or photographs |

Verified sample: May 2026, All Residential, unadjusted, `MEDIAN_SALE_PRICE=449846`, `HOMES_SOLD=464811`, `INVENTORY=1460440`, `MEDIAN_DOM=42`. Fields include `PERIOD_BEGIN`, `PERIOD_END`, `PROPERTY_TYPE`, `IS_SEASONALLY_ADJUSTED`, median prices, counts, pending sales, months of supply, sale-to-list ratio, price-drop share, and MoM/YoY variants. File rows are not chronological. Raw and seasonally adjusted series coexist, as do six property-type groups.

The current hub visibly advertised monthly tracker data last updated September 3, 2026 and an available range starting 2012 through August 2026 after its page initialized. Its Investor Home Purchases selector offered quarterly years 2000–2026; this suggests an additional possible 2008 series, **but no 2008 investor rows were downloaded or verified**. Neither the verified national tracker nor its current tracker UI provides 2008 property-level closings. Historical availability is dataset-specific.

**Engineering implication:** `realtykit/providers/redfin_research.py` ingests the legacy national file, marks it stale, and currently omits property-type and seasonal-adjustment dimensions from stored fact keys. Those dimensions need explicit filtering or storage before reliable comparisons. A successful data download also does not establish a commercial redisplay grant: the current [Redfin terms](https://www.redfin.com/about/terms-of-use) require review alongside any dataset-specific permission. The parent preserved this artifact and a provenance JSON in ignored local research storage; do not commit or redistribute it until rights are settled.

## RentCast can supply similar homes and active listings

The current API license expressly permits storing data and displaying/distributing it to third parties. API keys must stay confidential; upstream third-party obligations apply. No attribution is required by RentCast itself. Section 7 permits continued use of lawfully obtained data after termination subject to surviving terms, with possible deletion/cessation for legal or upstream obligations. Sections 3.3 and 6.3 limit assumptions about third-party content. This is a stronger explicit product-data grant than the reviewed ZTRAX/Redfin routes. [Current API license](https://www.rentcast.io/terms-api).

| Feature | Documented endpoint and behavior |
|---|---|
| Similar sale listings / valuation | [`GET /v1/avm/value`](https://developers.rentcast.io/reference/value-estimate): address or latitude/longitude; comparable listings sorted by descending `correlation`; filters include type, beds/baths/area, `maxRadius`, `daysOld`, `compCount` 5–25, and subject-attribute lookup |
| Similar rental listings / rent estimate | [`GET /v1/avm/rent/long-term`](https://developers.rentcast.io/reference/rent-estimate-long-term): corresponding rental comps and similarity order; estimate reflects expected long-term rent, not proof of an executed lease |
| Currently available homes | [`GET /v1/listings/sale`](https://developers.rentcast.io/reference/sale-listings): `status=Active`; address, city/state/ZIP or radius search; property type, bedrooms, bathrooms, area, lot, year, price and listing-age filters; most-recent `lastSeenDate` first |
| Currently available rentals | [`GET /v1/listings/rental/long-term`](https://developers.rentcast.io/reference/rental-listings-long-term): corresponding rental search and filters; `status=Active`; maximum 500 results per paginated response |
| Recorded property / last-sale lookup | [`GET /v1/properties`](https://developers.rentcast.io/reference/property-records): address/location search, attributes and sale history; `saleDateRange` is days since last sale, not an ISO date parameter; county/state field availability varies |

Use explicit `compCount`/`limit` because documentation shows conflicting UI defaults and prose defaults. Distinguish AVM comparable **listings** from recorded closed sales; `Inactive` only means off-market. The published [listing schema](https://developers.rentcast.io/reference/property-listings-schema) includes address, attributes, asking price/rent, dates, status, history and agent/office contacts. It lists **no photo/image or original-listing URL field**. Do not infer image rights or permission to copy content from linked sites from the API data grant. RealtyKit can begin with licensed factual cards, a similarity explanation, and freshness dates, then obtain a separate media source if required.

No RentCast key was requested, viewed, logged, or used in this research. Existing account activation, available quota, and actual local-market coverage remain for the parent app inspection.
