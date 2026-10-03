# New Jersey: recent recorded sales and the 2008 housing crisis

Analysis date: **October 2, 2026**. This report uses actual downloaded government files, with hashes and bounded acquisition recorded locally. It contains statewide and county aggregates, not buyer/seller details. All prices and index changes are nominal; no inflation adjustment, forecast, or causal claim is made.

## Findings

For the completed July 2025–June 2026 recording period, our screened NJ residential-sale sample has a **$542,000 median verified price across 59,843 records**, versus **$520,000 across 61,444** in July 2024–June 2025. The median increased **4.23%**, while the screened record count decreased **2.61%**. These are changes in the distribution of properties recorded and retained by this screening, **not same-home appreciation or all NJ market sales**. Calculated from the downloaded [2026](https://www.nj.gov/treasury/taxation/lpt/statdata/Sales2026.zip) and [2025](https://www.nj.gov/treasury/taxation/lpt/statdata/Sales2025.zip) SR1A files.

The independent FHFA purchase-only, seasonally adjusted NJ index increased **4.59% over one year** and **12.48% over two years**, through **2026Q2**. Around the 2008 crisis, it peaked in **2006Q2**, bottomed in **2012Q1**, and fell **23.02%**; it first recovered its prior nominal peak in **2020Q3**, 57 quarters or 14.25 years after the peak. These calculations describe a repeat-sales index, not transaction medians. [Official downloadable state series](https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_po_state.txt), [publisher's 2026Q2 summary corroborates the 4.59% annual change](https://www.fhfa.gov/house-price-index).

This demonstrates two feasible RealtyKit features: a **recorded-sale distribution explorer with screening controls**, and a **separate historical index panel** showing earlier drawdowns and recovery. Both need visible time coverage and source definitions. Neither dataset provides current listings, rents, or an individual home's valuation.

## Sources actually acquired

The canonical NJ Treasury catalog was updated October 1, 2026 and links the completed 2026 file; the older `/njbonds/` mirror is stale and should not drive acquisition. Current catalog links cover completed 2020–2026 files plus a YTD file. The completed-file labels are sales-ratio study years, not January–December sales years. [Canonical catalog](https://www.nj.gov/treasury/taxation/lpt/statdata.shtml).

| Download | Bytes | HTTP Last-Modified | Parsed records | Recording coverage used |
|---|---:|---|---:|---|
| [Sales2024.zip](https://www.nj.gov/treasury/taxation/lpt/statdata/Sales2024.zip) | 10,422,868 | October 1, 2024 | 167,598 | July 1, 2023–June 30, 2024 |
| [Sales2025.zip](https://www.nj.gov/treasury/taxation/lpt/statdata/Sales2025.zip) | 11,104,616 | October 1, 2025 | 171,949 | July 1, 2024–June 30, 2025 |
| [Sales2026.zip](https://www.nj.gov/treasury/taxation/lpt/statdata/Sales2026.zip) | 11,043,975 | October 1, 2026 | 170,664 | July 1, 2025–June 30, 2026 |
| [YTDSR1A2026.zip](https://www.nj.gov/treasury/taxation/lpt/statdata/YTDSR1A2026.zip) | 10,984,774 | August 12, 2026 | 169,935 | Maximum recording date June 30, 2026; overlaps the completed 2026 study |
| [FHFA purchase-only state TXT](https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_po_state.txt) | 263,057 | Not supplied | NJ series 1991Q1–2026Q2 | Calendar quarters; seasonally adjusted values used |
| [FHFA all-transactions state CSV](https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_state.csv) | 187,977 | Not supplied | NJ series 1975Q1–2026Q2 | Calendar quarters; not seasonally adjusted |

The current and historical SR1A layout PDFs and the May 2025 nonusable-sale guidelines were downloaded as well. Acquisition limits were 16 MiB per remote file, 50 MiB total compressed/source payload, and 150 MiB uncompressed contents per ZIP. Successful downloads had no credentials or charge. HTTP timestamps are publication evidence, not a promised future refresh schedule. The current completed 2026 study ends June 30 even though it was published October 1: no July–October 2026 sales claim is supported by these files.

For the crisis-era deed comparison, the current catalog did not expose a 2006–2012 transaction download. Seven bounded HEAD probes of **guessed** `Sales2006.zip` through `Sales2012.zip` paths returned HTTP 404. This establishes that those guessed paths were unavailable, **not that Treasury or county historical records do not exist**. The catalog offers an OPRA route for additional data; no request or external outreach was made. The crisis comparison therefore uses the directly downloadable federal index and cannot report 2008 NJ deed counts or median consideration.

## Keep the four clocks separate

1. **Study window:** July 1–June 30, defined by Treasury's sales-ratio program. The 2025 guidance explicitly gives July 1, 2024–June 30, 2025 as the current sampling period. [Official nonusable-sale guidelines](https://www.nj.gov/treasury/taxation/pdf/lpt/guidelines36.pdf).
2. **Recording date:** determines assignment to the study window. A property transferred earlier can be recorded later. Our tables and monthly CSV use recording date.
3. **Deed date:** retained separately in parsing and used to reject impossible deed-after-recording sequences. It is not substituted for the recording date or presented as a verified MLS closing date.
4. **Publication/snapshot date:** final 2026 ZIP October 1 versus the YTD ZIP August 12. The YTD label is not evidence of October year-to-date coverage. FHFA quarters have their own observation/release dates; its 2026Q2 report was published August 25. [FHFA release](https://www.fhfa.gov/reports/house-price-index/2026/Q2).

## Recent recorded-sale distributions

Primary screening uses NJ **class 2**, which includes dwellings for up to four families and residential condominiums; it is broader than detached single-family homes. [NJ assessor handbook, section 1005.01](https://www.nj.gov/treasury/taxation/pdf/assessorshandbook.pdf).

We retain a row when it is in the stated recording window, class 2, marked `U` (usable for the state sales-ratio study), has numeric verified price **greater than $1,000**, has no populated `ETC` marker or additional block/lot/qualifier identity, no critical flag `Y`/`1`, and has no deed date later than its recording date. Space/zero-only parcel-identity fields are treated as placeholders. This conservatively excludes flagged or possibly multiparcel records; it does not verify the true number of parcels. The $1,000 floor is discretionary screening, not an official arm's-length rule. We do not trim high prices. These files have no flagged critical errors, all dates parse, and no duplicate natural event keys were found. The natural key combines jurisdiction, serial, deed book/page, deed/recording dates, block/lot, and qualifier; it is a pragmatic duplicate check, not an official globally stable event identifier.

| Completed study | Recording period | Retained records | Median verified price | 25th percentile | 75th percentile |
|---|---|---:|---:|---:|---:|
| 2025 | July 2024–June 2025 | 61,444 | $520,000 | $353,500 | $750,000 |
| 2026 | July 2025–June 2026 | 59,843 | $542,000 | $370,000 | $770,000 |

The primary recent two-year analysis comprises the 2025 and 2026 study windows. The 2024 file is an additional screening diagnostic; it is not used for a two-year median change because its marker population differs substantially, as discussed below. Percentiles use linear interpolation. Record counts describe our retained sample, so their changes do not alone establish an equivalent change in total market activity.

Tax-study usability also depends on assessment circumstances. Code `27` can exclude a transaction occurring before a revaluation/reassessment, even when the transaction would otherwise be usable. We therefore expose the following sensitivity rather than equating every `N` code with an economically invalid sale. [Guidelines, category 27](https://www.nj.gov/treasury/taxation/pdf/lpt/guidelines36.pdf).

| Screening (same other filters) | 2025 records / median | 2026 records / median | Median change |
|---|---:|---:|---:|
| `U` only: headline | 61,444 / $520,000 | 59,843 / $542,000 | +4.23% |
| `U` plus `N` reason 27 | 71,103 / $530,000 | 69,460 / $555,000 | +4.72% |
| All positive-price class 2, regardless of usability | 103,856 / $495,000 | 101,018 / $520,000 | +5.05% |

The third row includes non-arm's-length and otherwise nonusable transactions; it is an acquisition diagnostic, not a preferred market series. Changing the headline nominal-price floor from $1,000 to $0 leaves both counts and medians unchanged. A $10,000 floor removes one 2026 row and leaves its median unchanged.

## County breakdown

The same `U` screening applies in each county. All 21 counties are represented, but their coverage can differ because of study classification and local assessment changes. Changes below compare July 2025–June 2026 with July 2024–June 2025, not calendar years or the same properties.

| County | 2025 count | 2025 median | 2026 count | 2026 median | Median change |
|---|---:|---:|---:|---:|---:|
| Atlantic | 2,571 | $338,000 | 3,127 | $360,000 | +6.51% |
| Bergen | 5,258 | $719,500 | 4,896 | $750,000 | +4.24% |
| Burlington | 4,296 | $375,000 | 4,086 | $390,000 | +4.00% |
| Camden | 3,871 | $316,000 | 4,124 | $350,000 | +10.76% |
| Cape May | 2,042 | $695,000 | 1,906 | $750,000 | +7.91% |
| Cumberland | 1,023 | $249,900 | 1,020 | $265,000 | +6.04% |
| Essex | 4,026 | $660,000 | 3,833 | $670,000 | +1.52% |
| Gloucester | 2,681 | $350,000 | 2,417 | $375,000 | +7.14% |
| Hudson | 3,532 | $668,850 | 3,422 | $700,000 | +4.66% |
| Hunterdon | 1,046 | $586,250 | 963 | $612,000 | +4.39% |
| Mercer | 2,494 | $429,000 | 2,136 | $470,000 | +9.56% |
| Middlesex | 4,657 | $530,000 | 4,642 | $550,000 | +3.77% |
| Monmouth | 3,037 | $715,000 | 2,761 | $750,000 | +4.90% |
| Morris | 3,664 | $661,000 | 3,407 | $687,500 | +4.01% |
| Ocean | 6,803 | $490,000 | 7,004 | $520,000 | +6.12% |
| Passaic | 3,088 | $555,000 | 2,634 | $600,000 | +8.11% |
| Salem | 506 | $245,000 | 581 | $260,000 | +6.12% |
| Somerset | 1,371 | $565,000 | 1,367 | $595,000 | +5.31% |
| Sussex | 1,360 | $434,500 | 1,427 | $449,999 | +3.57% |
| Union | 3,217 | $620,000 | 3,110 | $640,000 | +3.23% |
| Warren | 901 | $380,000 | 980 | $405,000 | +6.58% |

County and monthly tables for all three screening choices are saved locally. Monthly medians have no seasonal adjustment; comparisons of adjacent months should not be presented as appreciation.

## Crisis and recovery: a separate repeat-sales index

FHFA's purchase-only index measures repeated purchase transactions for single-family properties with mortgages acquired or securitized by Fannie Mae or Freddie Mac. It controls for changes in housing mix through its repeat-sales method, but does not represent every cash sale, jumbo-financed property, or housing type. The all-transactions sensitivity adds refinance appraisals. These index levels are not dollars. [FHFA methodology and coverage FAQ](https://www.fhfa.gov/faqs/hpi).

For a reproducible crisis definition, the script finds the maximum in **2000–2008**, the subsequent minimum through **2015**, and the first later quarter at or above the peak. Recovery is nominal index recovery, not recovery of an individual buyer's purchasing power or investment return. Searching through 2015 avoids artificially forcing the trough into 2008.

| Measure | Purchase-only, seasonally adjusted | All-transactions, not seasonally adjusted |
|---|---|---|
| Precrisis peak | 2006Q2: 257.26 | 2007Q1: 576.50 |
| Subsequent trough | 2012Q1: 198.04 | 2012Q2: 448.88 |
| Peak-to-trough change | −23.02% | −22.14% |
| First nominal recovery | 2020Q3: 260.28 | 2021Q1: 583.53 |
| Peak-to-recovery interval | 57 quarters / 14.25 years | 56 quarters / 14 years |
| 2024Q2 | 393.60 | 857.60 |
| 2025Q2 | 423.29 | 917.62 |
| Latest: 2026Q2 | 442.71 | 967.60 |
| Latest four-quarter change | +4.59% | +5.45% |
| Latest eight-quarter change | +12.48% | +12.83% |
| Latest versus precrisis peak | +72.09% | +67.84% |

Calculated directly from [purchase-only TXT](https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_po_state.txt) and [all-transactions CSV](https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_state.csv), frozen by local SHA-256 hashes. Series revisions can change historical levels; these results describe the downloaded vintage. Different coverage and seasonal treatment explain why these are separate sensitivities rather than interchangeable measures. The prior drawdown does not predict the next one.

The `ETC` marker is `X` in **73,102 raw 2024 rows**, versus blank in every 2025/2026 row. Checking the marker plus complete additional identities flags **22,417 additional raw usable class-2 2024 rows** compared with a block-only check; after the other filters, the retained count decreases by 22,415. The resulting conservative 2024 diagnostic is 36,063 records with a $435,000 median. A current verified definition explaining this cross-vintage difference was not found. This makes a simple 2024-to-2026 transaction-median comparison unsafe. The 2025/2026 headline counts and medians are unchanged by this strengthened screen.

The crisis was a multi-year decline rather than a fall confined to 2008. The purchase-only seasonally adjusted year-end values make that timing explicit:

| Quarter | Index | Change from same quarter a year earlier |
|---|---:|---:|
| 2006Q4 | 254.22 | +0.83% |
| 2007Q4 | 248.40 | −2.29% |
| 2008Q4 | 227.17 | −8.55% |
| 2009Q4 | 216.92 | −4.51% |
| 2010Q4 | 211.01 | −2.72% |
| 2011Q4 | 199.18 | −5.61% |
| 2012Q4 | 198.30 | −0.44% |

## Numeric quality and preliminary-file revisions

| Check | 2024 final | 2025 final | 2026 final |
|---|---:|---:|---:|
| Raw/unique event rows | 167,598 | 171,949 | 170,664 |
| Class 2 rows before screening | 141,755 | 145,467 | 145,645 |
| Records outside stated study window | 22 | 21 | 101 |
| Deed-after-recording anomalies, all classes | 12 | 1 | 6 |
| Reported versus verified price differences | 94 | 0 | 0 |
| Malformed row length, bad county, duplicate key | 0 | 0 | 0 |

Every parsed record in all four ZIPs is **663 characters**, and every recording date parses as **YYMMDD**. None parses as MMDDYY. The old descriptive PDF says MMDDYY; applying it to current files would fail. The newer layout also shifts the year-built/living-area positions relative to the older description. The parser uses the current byte positions and validates lengths and dates, rather than blindly treating the historical PDF as the current contract. [Current layout](https://www.nj.gov/treasury/taxation/pdf/lpt/SR1Afilelayout.pdf), [historical description](https://www.nj.gov/treasury/taxation/pdf/lpt/SR1A_FileLayout_Description.pdf).

A small number of historical/sentinel deed dates appear in raw files. We do not claim those are genuine mid-century market transactions. Out-of-window records and impossible date sequences are excluded from the recent samples. Date plausibility, address matching, missing unit characteristics, and completeness against county sources still need validation before a property-level public product.

The YTD and final 2026 files share **169,883 natural event keys**. There are **52 keys only in YTD** and **781 only in final**. Among the common keys, **6,360 usability flags**, **6,747 nonusable reason codes**, and **one verified price** changed. These figures are independent comparisons and can overlap. Because the key includes dates and parcel identifiers, an identity correction can appear as removal/addition; these are not definitive counts of newly closed homes. **Use the completed file for this analysis; never append YTD as a second set of 2026 transactions.**

Verification included SHA-256 checks against the acquisition manifest, successful parsing of all 680,146 downloaded sale rows, a separate streaming recomputation of all three `U` counts and medians, reconciliation of all nine statewide summaries against county and monthly counts, and agreement of the computed purchase-only annual change with FHFA's published 4.59% summary.

## Reproduction and local outputs

From the repository root, using Python 3 standard library only:

```sh
python3 scripts/research/nj_recent_and_crisis.py acquire
python3 scripts/research/nj_recent_and_crisis.py analyze
```

The first command needs network access to the official state/federal hosts; it checks bounds, records provenance, and reuses only hash-matching cached files. The second performs local analysis after verifying all source hashes. The script is [nj_recent_and_crisis.py](../../../scripts/research/nj_recent_and_crisis.py).

Generated files under `data/research/nj-2026-10-02/` (local only, excluded from Git):

- `provenance.json`: acquisition provenance and SHA-256 hashes
- `results.json`: structured results and quality diagnostics
- `nj_sr1a_study_summary.csv`: statewide study summaries
- `nj_sr1a_county_summary.csv`: county summaries
- `nj_sr1a_monthly_summary.csv`: recording-month summaries
- `nj_fhfa_quarterly.csv`: NJ quarterly index values from 2000 onward

Raw downloads and generated results live under ignored `data/research/`; names and mailing addresses present in raw state records are neither printed nor exported into the generated aggregates. This local research did not import data into the app, schedule downloads, contact anyone, or resolve rights for public record-level display. A production feature should preserve publisher/source dates, screening reasons and privacy redactions, and complete the public-display review identified in the broader research.
