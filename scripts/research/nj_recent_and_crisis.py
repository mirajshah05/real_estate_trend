"""Bounded official NJ sale-file/FHFA acquisition and reproducible local analysis.

Raw government files may contain names and mailing addresses; all generated
outputs are aggregates or federal index values. No owner data is printed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data/research/nj-2026-10-02"
BASE = "https://www.nj.gov/treasury/taxation/lpt/statdata/"
SOURCES = {
    **{name: BASE + name for name in (
        "YTDSR1A2026.zip", "Sales2026.zip", "Sales2025.zip", "Sales2024.zip")},
    "SR1Afilelayout.pdf": "https://www.nj.gov/treasury/taxation/pdf/lpt/SR1Afilelayout.pdf",
    "SR1A_FileLayout_Description.pdf": "https://www.nj.gov/treasury/taxation/pdf/lpt/SR1A_FileLayout_Description.pdf",
    "guidelines36.pdf": "https://www.nj.gov/treasury/taxation/pdf/lpt/guidelines36.pdf",
    "hpi_po_state.txt": "https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_po_state.txt",
    "hpi_at_state.csv": "https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_state.csv",
}
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 50 * 1024 * 1024
MAX_UNCOMPRESSED_ZIP = 150 * 1024 * 1024
COUNTIES = dict(enumerate(("Atlantic", "Bergen", "Burlington", "Camden", "Cape May",
    "Cumberland", "Essex", "Gloucester", "Hudson", "Hunterdon", "Mercer", "Middlesex",
    "Monmouth", "Morris", "Ocean", "Passaic", "Salem", "Somerset", "Sussex", "Union", "Warren"), 1))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def acquire(folder):
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "provenance.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        "analysis_as_of": "2026-10-02", "sources": {}, "historical_probes": []}
    total = sum(p.stat().st_size for p in folder.iterdir() if p.name in SOURCES)
    for name, url in SOURCES.items():
        target = folder / name
        if target.exists():
            assert name in manifest["sources"], f"Unprovenanced file: {target}"
            assert hashlib.sha256(target.read_bytes()).hexdigest() == manifest["sources"][name]["sha256"]
            print(f"Cached {name}: {target.stat().st_size:,} bytes")
            continue
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=45) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_FILE:
                raise ValueError(f"Source too large: {name}")
            metadata = {"url": url, "head_status": response.status,
                        "last_modified": response.headers.get("Last-Modified"),
                        "content_type": response.headers.get("Content-Type"),
                        "declared_bytes": int(length) if length else None}
        chunks = []
        size = 0
        with urllib.request.urlopen(url, timeout=60) as response:
            while chunk := response.read(256 * 1024):
                size += len(chunk)
                if size > MAX_FILE or total + size > MAX_TOTAL:
                    raise ValueError("Acquisition byte limit exceeded")
                chunks.append(chunk)
        payload = b"".join(chunks)
        if name.endswith(".zip"):
            assert payload[:2] == b"PK", f"Not a zip: {name}"
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                assert sum(i.file_size for i in archive.infolist()) <= MAX_UNCOMPRESSED_ZIP
                metadata["members"] = [{"name": i.filename, "bytes": i.file_size}
                                       for i in archive.infolist()]
        target.write_bytes(payload)
        total += size
        metadata.update({"bytes": size, "sha256": hashlib.sha256(payload).hexdigest(),
                         "retrieved_at_utc": datetime.now(UTC).isoformat()})
        manifest["sources"][name] = metadata
        write_json(manifest_path, manifest)
        print(f"Downloaded {name}: {size:,} bytes")
    if not manifest["historical_probes"]:
        for year in range(2006, 2013):
            url = BASE + f"Sales{year}.zip"
            record = {"url": url, "method": "HEAD", "guessed_path_not_catalog_link": True}
            try:
                with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
                    record.update({"status": r.status, "bytes": r.headers.get("Content-Length")})
            except urllib.error.HTTPError as e:
                record["status"] = e.code
            except urllib.error.URLError as e:
                record["error"] = str(e.reason)
            manifest["historical_probes"].append(record)
            write_json(manifest_path, manifest)
        print("Historical filename probes recorded; missing paths do not prove records do not exist.")


def numeric(raw):
    value = raw.strip()
    return int(value) if value.isdigit() else None


def sr_date(raw, format="YYMMDD"):
    if len(raw) != 6 or not raw.isdigit() or raw == "000000":
        return None
    a, b, c = (int(raw[i:i+2]) for i in (0, 2, 4))
    year, month, day = (a, b, c) if format == "YYMMDD" else (c, a, b)
    try:
        return date(2000 + year if year <= 49 else 1900 + year, month, day)
    except ValueError:
        return None


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * q
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def price_stats(rows):
    prices = [r["price"] for r in rows]
    return {"count": len(prices), "median_price": median(prices) if prices else None,
            "p25_price": quantile(prices, .25), "p75_price": quantile(prices, .75)}


def read_sales(folder, name):
    """Read only nonpersonal fields at positions in the current 663-byte layout."""
    rows, seen = [], set()
    qc = Counter()
    classes, uses, errors, reasons = Counter(), Counter(), Counter(), Counter()
    lengths = Counter()
    with zipfile.ZipFile(folder / name) as archive:
        assert sum(i.file_size for i in archive.infolist()) <= MAX_UNCOMPRESSED_ZIP
        for info in archive.infolist():
            if not info.filename.lower().endswith(".txt"):
                continue
            with archive.open(info) as source:
                for payload in source:
                    raw = payload.rstrip(b"\r\n").decode("ascii")
                    qc["source_rows"] += 1
                    lengths[len(raw)] += 1
                    if len(raw) != 663:
                        qc["malformed_length"] += 1
                        continue
                    recorded = sr_date(raw[344:350])
                    deed = sr_date(raw[338:344])
                    qc["recorded_valid_yymmdd"] += recorded is not None
                    qc["recorded_valid_mmddyy"] += sr_date(raw[344:350], "MMDDYY") is not None
                    qc["deed_valid_yymmdd"] += deed is not None
                    if recorded and deed:
                        qc["deed_after_recording"] += deed > recorded
                    county = numeric(raw[0:2])
                    if county not in COUNTIES:
                        qc["bad_county"] += 1
                        continue
                    property_class = raw[626:629].strip()
                    usable = raw[33:34]
                    reason = raw[34:37].strip()
                    critical = raw[648:649].strip()
                    classes[property_class] += 1
                    uses[usable] += 1
                    errors[critical] += 1
                    if property_class == "2" and usable == "N":
                        reasons[reason] += 1
                    reported = numeric(raw[37:46])
                    price = numeric(raw[46:55])
                    qc["nonnumeric_verified_price"] += price is None
                    qc["reported_verified_price_differ"] += reported != price
                    # Never save names, mailing address or situs into generated output.
                    key = (raw[:4], raw[98:105], raw[328:338], raw[338:350], raw[350:369], raw[619:624])
                    if key in seen:
                        qc["duplicate_event_keys"] += 1
                        continue
                    seen.add(key)
                    # ETC is position 369 (1-based); each additional parcel has
                    # block + lot + qualifier (23 characters), followed by values.
                    # Space/zero-only fields are publisher placeholders. Check the
                    # full identity, including lot-only or qualifier-only entries.
                    additional_parcels = bool(raw[368].strip(" 0")) or any(
                        raw[a:a+23].strip(" 0") for a in (369, 419, 469, 519, 569))
                    rows.append({"key": key, "county": county, "property_class": property_class,
                                 "usable": usable, "reason": reason, "critical": critical,
                                 "price": price, "reported_price": reported,
                                 "recorded": recorded, "deed": deed,
                                 "multi_parcel": bool(additional_parcels)})
    dates = [r["recorded"] for r in rows if r["recorded"]]
    deeds = [r["deed"] for r in rows if r["deed"]]
    qc = dict(qc)
    qc.update({"source_file": name, "unique_rows": len(rows), "row_lengths": dict(lengths),
               "recorded_min": min(dates).isoformat(), "recorded_max": max(dates).isoformat(),
               "deed_min": min(deeds).isoformat(), "deed_max": max(deeds).isoformat(),
               "property_classes": dict(classes), "usability": dict(uses),
               "critical_error_flags": dict(errors), "residential_nonusable_reasons": dict(reasons)})
    assert not qc.get("malformed_length") and not qc.get("bad_county")
    # Every current recording date must parse; old MMDDYY descriptions do not match current files.
    assert qc["recorded_valid_yymmdd"] == qc["source_rows"]
    return rows, qc


def eligible(row, start, end, screening="usable", nominal_floor=1000):
    return (row["property_class"] == "2" and row["recorded"] is not None
            and start <= row["recorded"] <= end
            and row["price"] is not None and row["price"] > nominal_floor
            and (row["deed"] is None or row["deed"] <= row["recorded"])
            and row["critical"] not in ("Y", "1") and not row["multi_parcel"]
            and (screening == "all_positive" or row["usable"] == "U"
                 or (screening == "usable_plus_nu27" and row["reason"].lstrip("0") == "27")))


def index_stats(series):
    def label(point):
        yr, quarter, value = point
        return {"quarter": f"{yr}Q{quarter}", "value": value}
    # Fixed precrisis window; subsequent trough search extends through 2015 to avoid forcing 2008.
    peak = max((p for p in series if 2000 <= p[0] <= 2008), key=lambda p: p[2])
    trough = min((p for p in series if (p[0], p[1]) > peak[:2] and p[0] <= 2015), key=lambda p: p[2])
    recovery = next((p for p in series if p[:2] > trough[:2] and p[2] >= peak[2]), None)
    lookup = {(p[0], p[1]): p for p in series}
    last = series[-1]
    one_year = lookup[(last[0]-1, last[1])]
    two_year = lookup[(last[0]-2, last[1])]
    return {"precrisis_peak": label(peak), "subsequent_trough": label(trough),
            "drawdown_pct": 100*(trough[2]/peak[2]-1),
            "recovered_precrisis_peak": label(recovery) if recovery else None,
            "quarters_peak_to_recovery": ((recovery[0]-peak[0])*4+recovery[1]-peak[1]) if recovery else None,
            "latest": label(last), "one_year_prior": label(one_year), "two_year_prior": label(two_year),
            "one_year_change_pct": 100*(last[2]/one_year[2]-1),
            "two_year_change_pct": 100*(last[2]/two_year[2]-1),
            "latest_above_precrisis_peak_pct": 100*(last[2]/peak[2]-1)}


def write_csv(path, records):
    with path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def analyze(folder):
    manifest = json.loads((folder / "provenance.json").read_text())
    for name, metadata in manifest["sources"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == metadata["sha256"]
    po = []
    with (folder / "hpi_po_state.txt").open() as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["state"] == "NJ":
                po.append((int(row["yr"]), int(row["qtr"]), float(row["indx_sa"])))
    at = []
    with (folder / "hpi_at_state.csv").open() as source:
        for state, year, quarter, value in csv.reader(source):
            if state == "NJ":
                at.append((int(year), int(quarter), float(value)))
    po.sort(); at.sort()
    assert len({x[:2] for x in po}) == len(po) and len({x[:2] for x in at}) == len(at)
    indexes = {"purchase_only_seasonally_adjusted": index_stats(po),
               "all_transactions_not_seasonally_adjusted": index_stats(at)}
    index_rows = []
    for kind, series in (("purchase_only_sa", po), ("all_transactions_nsa", at)):
        lookup = {p[:2]: p[2] for p in series}
        for year, quarter, value in series:
            if year >= 2000:
                prior = lookup.get((year-1, quarter))
                index_rows.append({"series": kind, "quarter": f"{year}Q{quarter}", "index": value,
                                   "yoy_change_pct": 100*(value/prior-1) if prior else None})
    write_csv(folder / "nj_fhfa_quarterly.csv", index_rows)
    quality, summaries, county_rows, monthly_rows, loaded = [], [], [], [], {}
    for study in (2024, 2025, 2026):
        name = f"Sales{study}.zip"
        rows, qc = read_sales(folder, name)
        quality.append(qc)
        loaded[study] = rows
        start, end = date(study-1, 7, 1), date(study, 6, 30)
        qc["outside_study_window"] = sum(not(start <= r["recorded"] <= end) for r in rows)
        assert qc["outside_study_window"] / len(rows) < .002
        for screening in ("usable", "usable_plus_nu27", "all_positive"):
            selected = [r for r in rows if eligible(r, start, end, screening)]
            summary = {"study_year": study, "recorded_start": start.isoformat(),
                       "recorded_end": end.isoformat(), "screening": screening, **price_stats(selected)}
            summaries.append(summary)
            for county, county_name in COUNTIES.items():
                county_rows.append({"study_year": study, "county_code": county,
                                    "county": county_name, "screening": screening,
                                    **price_stats([r for r in selected if r["county"] == county])})
            by_month = defaultdict(list)
            for row in selected:
                by_month[row["recorded"].strftime("%Y-%m")].append(row)
            for month, group in sorted(by_month.items()):
                monthly_rows.append({"study_year": study, "recorded_month": month,
                                     "screening": screening, **price_stats(group)})
    ytd, ytd_qc = read_sales(folder, "YTDSR1A2026.zip")
    quality.append(ytd_qc)
    final = {r["key"]: r for r in loaded[2026]}
    preliminary = {r["key"]: r for r in ytd}
    common = set(final) & set(preliminary)
    revision = {"ytd_rows": len(ytd), "final_rows": len(final), "common_keys": len(common),
                "only_ytd_keys": len(set(preliminary)-set(final)),
                "only_final_keys": len(set(final)-set(preliminary)),
                "usability_changed": sum(final[k]["usable"] != preliminary[k]["usable"] for k in common),
                "verified_price_changed": sum(final[k]["price"] != preliminary[k]["price"] for k in common),
                "nonusable_reason_changed": sum(final[k]["reason"] != preliminary[k]["reason"] for k in common)}
    # Fixed screening sensitivity distinguishes tax-study exclusion from economic exclusion.
    sensitivities = []
    for study in (2025, 2026):
        for floor in (0, 1000, 10000):
            selected = [r for r in loaded[study] if eligible(r, date(study-1,7,1),date(study,6,30),
                                                           "usable", floor)]
            sensitivities.append({"study_year": study, "nominal_floor": floor, **price_stats(selected)})
    write_csv(folder / "nj_sr1a_study_summary.csv", summaries)
    write_csv(folder / "nj_sr1a_county_summary.csv", county_rows)
    write_csv(folder / "nj_sr1a_monthly_summary.csv", monthly_rows)
    result = {"analysis_as_of": "2026-10-02", "date_encoding_current_files": "YYMMDD",
              "price_definition": "verified sale price, nominal USD, class 2 residential",
              "price_filters": "price > $1,000; no populated ETC or additional block/lot/qualifier identities (space/zero placeholders ignored); critical flag not Y/1; deed not after recording",
              "time_basis": "recording date, July-June study periods; not calendar-year closings",
              "indexes": indexes, "study_summaries": summaries, "quality": quality,
              "preliminary_vs_final": revision, "nominal_threshold_sensitivity": sensitivities,
              "source_sha256": {k:v["sha256"] for k,v in manifest["sources"].items()}}
    write_json(folder / "results.json", result)
    print(json.dumps({"indexes": indexes, "study_summaries": summaries,
                      "quality": quality, "preliminary_vs_final": revision,
                      "nominal_threshold_sensitivity": sensitivities}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("acquire", "analyze"))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    (acquire if args.action == "acquire" else analyze)(args.data_dir)


if __name__ == "__main__":
    main()
