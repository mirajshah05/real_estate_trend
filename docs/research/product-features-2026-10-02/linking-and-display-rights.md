# Linking and displaying third-party housing content

Research date: October 2, 2026. Scope: US RealtyKit, currently a local research dashboard; a public or commercial product would have a different use context. This is a product/data-access assessment of published terms, not a legal opinion on their enforceability. Provider permission, underlying content rights, and applicable law all matter.

## Recommended approach

Show property facts obtained from official records or a licensed API, calculations produced by RealtyKit, and clearly identified sources. Add outbound listing links only where the relevant provider's conditions and the source of the URL permit them. A click-through link does not authorize importing that site's listing card, photo, description, or prices. Source citations in research documentation are distinct from deploying an automated listing-link feature.

For displaying live home/rental records inside the app, RentCast already has an adapter and its current API license expressly permits storage and third-party display, subject to its other conditions. For authoritative MLS coverage and media, obtain the regional MLS/vendor agreement or a publisher agreement that covers the proposed product. Do not infer permission from an API returning a photo URL, from a public website, from attribution alone, or from the license on a GitHub scraper.

## What each integration means

| Integration | What RealtyKit displays | Practical permission position |
|---|---|---|
| Plain outbound link | A provider name and a URL; user opens the original site | Potentially feasible, but provider linking clauses differ; see below |
| Own property card plus link | Official/licensed address and sale facts, RealtyKit calculations, external navigation | Card data and URL each need their own valid source; record attribution and permission |
| Portal-derived preview | Portal photo, description, listing price, logo, or thumbnail | Republishing content; an outbound link does not supply this license |
| Embedded portal page | Iframe, webview, screenshot, or server proxy inside our experience | Technical availability is not permission; Realtor.com explicitly prohibits framing in its linking conditions |
| Research charts | Charts derived from expressly downloadable aggregate research | Follow dataset-specific permission and attribution; not a property-listing feed |
| Licensed API/MLS card | Fields and media supplied under a contract | Implement the contract's permitted display, retention, refresh, broker attribution, status and media rules |

## Provider-specific outbound-link findings

| Provider | Published terms relevant to linking | Product recommendation |
|---|---|---|
| Zillow, including its affiliated brands | Section 5 restricts third-party links unless the originating site is real-estate-related and owned/operated by a real-estate or lending professional or institution. Sections 4–5 separately restrict redisplay, automated extraction, and competing-product use. | Do not launch a blanket Zillow listing-link button on the assumption that RealtyKit's housing topic qualifies its operator. Resolve the operator qualification or obtain permission. |
| Realtor.com / Move | Deep links require express written permission. Its homepage exception requires prior written notice, prominent attribution, and compliance with other conditions, including no framing. | Do not generate deep links to individual listings without permission. Follow the notice process for the homepage exception. Research-library attribution requirements should be evaluated in that specific context. |
| Apartments.com | Linking section expressly permits homepage and other canonical-page URLs without manipulating necessary values, parameters or subfolders; the right is revocable. The opening terms also require the user not to be a competitor. | Strongest explicit consumer-site link provision found, but resolve the competitor condition for a public housing/rental product. Use original canonical URLs; permission to link does not grant listing-content reuse. |
| Compass | Section 10 acknowledges incoming links; sections 5–6 restrict non-personal content reuse, scraping and derivative datasets. No explicit general inbound-link ban was found in the reviewed terms. | A plain link is a candidate, not an affirmative integration license. Seek written clarification before systematic commercial linking or content integration. |
| Redfin | Sections 2.3.4–2.3.5 deny general third-party display rights and prohibit automated extraction without permission. No general inbound-link prohibition was located in the reviewed terms. | Plain click-through is a candidate subject to final review; do not scrape to discover listing URLs or copy cards. Data Center downloads are a separate aggregate-research pathway. |

Sources: [Zillow terms, updated October 28, 2025](https://www.zillow.com/corporate/terms-of-use/); [Realtor.com terms, linking paragraphs](https://www.realtor.com/terms-of-service/); [Apartments.com terms, opening and Linking sections](https://www.apartments.com/grow/about/terms-of-service); [Compass terms, updated July 27, 2026](https://www.compass.com/legal/terms-of-service); [Redfin terms, updated September 29, 2025](https://www.redfin.com/about/terms-of-use).

The absence of an identified restriction is not a legal guarantee or a signed permission. Contract formation/enforceability is a separate legal question; this research does not rely on challenging provider terms as the access strategy. None of these findings authorizes bypassing login gates or anti-bot measures.

## Licensed paths for in-app display

### RentCast: best fit with the existing implementation

The current API license's section 1 permits internal analytics, storage, and third-party disclosure/display/distribution. Sections 3.3 and 6 retain third-party data/content conditions; section 2 requires reasonable measures against unauthorized scraping. Section 7 allows continued use of lawfully obtained data after termination within the surviving terms, while preserving legally required deletion. Keys remain confidential. The API-data grant does not independently license every third-party media asset linked from a response. RealtyKit should verify any media separately and retain contract/source provenance. [RentCast API license](https://www.rentcast.io/terms-api).

The local app already stores sanitized records and enforces a hard limit of 40 attempted API calls per calendar month. That is a RealtyKit implementation constraint, not a nationwide bulk-data strategy or a statement of RentCast's current plan allowance. A small targeted property workspace fits this budget better than repeated map-wide collection.

### Zillow/Bridge: an approval-based API path

Current Bridge documentation includes the Zillow Economic Data API and public-record/MLS products. These are separate from anonymous Research CSV downloads. Zillow's current API terms require written app/competitive-product permission and impose product-specific attribution, end-user caching/export restrictions and termination deletion. A downloadable research chart, an API token and MLS authorization are distinct permission contexts. Review the actual product terms before choosing an offline store or export design. [Bridge documentation](https://bridgedataoutput.com/docs/platform/Introduction), [Zillow API terms](https://bridgedataoutput.com/zillowterms), [detailed dataset note](vendor-datasets.md).

### MLS / RESO / IDX: authoritative listings under licensed uses

RESO is a technical standard, not a universal data license. IDX policy provides display rights through qualified MLS participants and their approved vendors. Broker identity, listing attribution, allowed fields, updates, withdrawn records, and local MLS conditions govern the display. Analytics, sold-history retention, exports and public media access may need additional rights; an IDX feed should not be assumed to license all of them. [NAR IDX policy, 2026](https://www.nar.realtor/handbook-on-multiple-listing-policy/advertising-print-and-electronic-section-1-internet-data-exchange-idx-policy-policy-statement-7-58), [RESO discussion of use rights](https://www.reso.org/blog/one-feed-rule-them-all/), [RESO media permissions](https://www.reso.org/blog/media-permissions-private-photos/).

### ListHub: evaluate only if consumer listing display becomes the product

ListHub screens publishers for advertising value to brokers and requires a publisher agreement. Its published requirements include minimum display fields, preserving source priority, routing leads to the designated broker/agent, and limits on resyndication. Its display-focused pathway is not blanket permission for offline analytics, sold history, or redistribution. [ListHub publisher network and conditions](https://www.listhub.com/publisher-network/).

## Concrete feature design

1. A user adds a property by address and optionally saves an external URL. RealtyKit stores its own notes, independent official/licensed facts, and calculations; it does not auto-fetch a listing preview.
2. A property dossier shows address, parcel identifier, dated sale events, origin of each price, and comparable-record filters. Owner/contact fields are excluded unless a later feature has a justified and permitted use.
3. External navigation uses a plain text provider label and the original authorized URL, opens the original site normally, and conveys no affiliation. Provider-specific policies decide whether a link can be offered.
4. Photos appear only when the actual media rights and relevant status/retention rules are established. A photo URL is not a substitute for this check.
5. A source permission record tracks `internal_cache`, `public_display`, `raw_export`, `derived_analytics`, `media_display`, `outbound_link`, required attribution, expiry/deletion rules, and the governing source/contract version. This is proposed implementation metadata, not existing functionality.

No provider was contacted, no permission request was sent, no account or paid plan was activated, and no application behavior was changed during this research.
