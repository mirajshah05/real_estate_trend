#!/usr/bin/env python3
"""Live data-extraction probes for RealtyKit (as-of 2026-08-31)."""
from __future__ import annotations

import csv
import gzip
import io
import json
import ssl
import sys
import time
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TODAY = date(2026, 8, 31)
OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
RESULTS = OUT / "probe_results.json"
CTX = ssl.create_default_context()
UA = "RealtyKitResearch/0.1 (data-extraction assessor; educational)"


def head(url: str, timeout: int = 30) -> dict:
    req = Request(url, method="HEAD", headers={"User-Agent": UA})
    t0 = time.time()
    try:
        with urlopen(req, timeout=timeout, context=CTX) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return {
                "url": url,
                "status": resp.status,
                "content_length": headers.get("content-length"),
                "last_modified": headers.get("last-modified"),
                "content_type": headers.get("content-type"),
                "etag": headers.get("etag"),
                "elapsed_s": round(time.time() - t0, 3),
            }
    except HTTPError as e:
        headers = {k.lower(): v for k, v in e.headers.items()} if e.headers else {}
        return {
            "url": url,
            "status": e.code,
            "content_length": headers.get("content-length"),
            "last_modified": headers.get("last-modified"),
            "error": str(e),
            "elapsed_s": round(time.time() - t0, 3),
        }
    except Exception as e:
        return {"url": url, "status": None, "error": repr(e), "elapsed_s": round(time.time() - t0, 3)}


def download(url: str, dest: Path, timeout: int = 60, max_bytes: int | None = None) -> dict:
    req = Request(url, headers={"User-Agent": UA})
    t0 = time.time()
    try:
        with urlopen(req, timeout=timeout, context=CTX) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            cl = headers.get("content-length")
            if max_bytes and cl and int(cl) > max_bytes:
                return {
                    "url": url,
                    "status": resp.status,
                    "skipped": True,
                    "reason": f"content-length {cl} exceeds max_bytes {max_bytes}",
                    "content_length": cl,
                    "last_modified": headers.get("last-modified"),
                    "elapsed_s": round(time.time() - t0, 3),
                }
            data = resp.read() if not max_bytes else resp.read(max_bytes)
            dest.write_bytes(data)
            return {
                "url": url,
                "status": resp.status,
                "bytes": dest.stat().st_size,
                "content_length": cl,
                "last_modified": headers.get("last-modified"),
                "path": str(dest),
                "elapsed_s": round(time.time() - t0, 3),
            }
    except Exception as e:
        return {"url": url, "status": None, "error": repr(e), "elapsed_s": round(time.time() - t0, 3)}


def stream_gzip_first_match(
    url: str,
    dest_sample: Path,
    match_fn,
    max_read: int = 8_000_000,
    timeout: int = 45,
) -> dict:
    """Stream a gzip TSV and keep only the header + first matching data row."""
    req = Request(url, headers={"User-Agent": UA})
    t0 = time.time()
    try:
        with urlopen(req, timeout=timeout, context=CTX) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            raw = resp.read(max_read)
            # Try to decompress what we have; may be truncated gzip
            try:
                text = gzip.decompress(raw).decode("utf-8", errors="replace")
                truncated = False
            except Exception:
                # Incomplete gzip stream — use GzipFile incrementally
                bio = io.BytesIO(raw)
                chunks = []
                try:
                    with gzip.GzipFile(fileobj=bio) as gf:
                        while True:
                            c = gf.read(65536)
                            if not c:
                                break
                            chunks.append(c)
                    text = b"".join(chunks).decode("utf-8", errors="replace")
                    truncated = False
                except Exception as de:
                    if chunks:
                        text = b"".join(chunks).decode("utf-8", errors="replace")
                        truncated = True
                    else:
                        return {
                            "url": url,
                            "status": resp.status,
                            "error": f"gzip decompress failed: {de!r}",
                            "bytes_read": len(raw),
                            "content_length": headers.get("content-length"),
                            "last_modified": headers.get("last-modified"),
                            "elapsed_s": round(time.time() - t0, 3),
                        }
            lines = text.splitlines()
            if not lines:
                return {"url": url, "status": resp.status, "error": "empty after decompress"}
            reader = csv.DictReader(lines, delimiter="\t")
            cols = reader.fieldnames
            match = None
            scanned = 0
            for row in reader:
                scanned += 1
                if match_fn(row):
                    match = row
                    break
            dest_sample.write_text(
                json.dumps({"columns": cols, "scanned_rows": scanned, "match": match}, indent=2),
                encoding="utf-8",
            )
            return {
                "url": url,
                "status": resp.status,
                "bytes_read": len(raw),
                "content_length": headers.get("content-length"),
                "last_modified": headers.get("last-modified"),
                "columns": cols,
                "scanned_rows": scanned,
                "match": match,
                "truncated_gzip": truncated,
                "elapsed_s": round(time.time() - t0, 3),
            }
    except HTTPError as e:
        return {"url": url, "status": e.code, "error": str(e), "elapsed_s": round(time.time() - t0, 3)}
    except Exception as e:
        return {"url": url, "status": None, "error": repr(e), "elapsed_s": round(time.time() - t0, 3)}


def parse_zillow_wide(path: Path, targets: list[str]) -> dict:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        date_cols = [c for c in cols if c[:4].isdigit() and "-" in c]
        latest = date_cols[-1] if date_cols else None
        rows = list(reader)
    found = {}
    for row in rows:
        name = (row.get("RegionName") or "").strip()
        if name in targets or any(t.lower() in name.lower() for t in targets):
            found[name] = {
                "RegionID": row.get("RegionID"),
                "RegionType": row.get("RegionType"),
                "StateName": row.get("StateName"),
                "latest": row.get(latest) if latest else None,
            }
    age = None
    if latest:
        try:
            d = date.fromisoformat(latest)
            age = (TODAY - d).days
        except ValueError:
            age = None
    return {
        "file": str(path),
        "bytes": path.stat().st_size,
        "metro_count": len(rows),
        "id_cols": [c for c in cols if c not in date_cols],
        "week_count": len(date_cols),
        "first_week": date_cols[0] if date_cols else None,
        "latest_week": latest,
        "age_days_vs_2026_08_31": age,
        "targets": found,
        "sample_region_names": [r.get("RegionName") for r in rows[:8]],
    }


def parse_fred_tail(path: Path, n: int = 5) -> dict:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    last = rows[-n:] if rows else []
    latest = last[-1] if last else None
    age = None
    if latest:
        obs = latest.get("observation_date") or latest.get("DATE") or list(latest.values())[0]
        try:
            d = date.fromisoformat(str(obs)[:10])
            age = (TODAY - d).days
        except ValueError:
            age = None
    return {
        "file": str(path),
        "bytes": path.stat().st_size,
        "row_count": len(rows),
        "last_n": last,
        "age_days_vs_2026_08_31": age,
    }


def parse_yahoo(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = data["chart"]["result"][0]
    meta = result["meta"]
    ts = result.get("timestamp") or []
    closes = (result.get("indicators") or {}).get("quote", [{}])[0].get("close") or []
    last_close = None
    last_ts = None
    for t, c in zip(reversed(ts), reversed(closes)):
        if c is not None:
            last_close = c
            last_ts = t
            break
    last_date = datetime.utcfromtimestamp(last_ts).date().isoformat() if last_ts else None
    age = None
    if last_date:
        age = (TODAY - date.fromisoformat(last_date)).days
    return {
        "symbol": meta.get("symbol"),
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
        "last_close": last_close,
        "last_date": last_date,
        "regular_market_price": meta.get("regularMarketPrice"),
        "regular_market_time": meta.get("regularMarketTime"),
        "age_days_vs_2026_08_31": age,
        "points": len(ts),
    }


def main() -> int:
    report: dict = {"as_of": TODAY.isoformat(), "probes": {}}

    redfin_urls = {
        "national": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/us_national_market_tracker.tsv000.gz",
        "metro": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/redfin_metro_market_tracker.tsv000.gz",
        "metro_alt": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/us_metro_market_tracker.tsv000.gz",
        "city": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/city_market_tracker.tsv000.gz",
        "city_alt": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/us_city_market_tracker.tsv000.gz",
        "zip": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/zip_code_market_tracker.tsv000.gz",
        "zip_alt": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/us_zip_code_market_tracker.tsv000.gz",
        "state": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/state_market_tracker.tsv000.gz",
        "county": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/county_market_tracker.tsv000.gz",
        "neighborhood": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/neighborhood_market_tracker.tsv000.gz",
        "weekly": "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_covid19/weekly_housing_market_data_most_recent.tsv000.gz",
    }
    print("=== HEAD Redfin ===", flush=True)
    report["probes"]["redfin_heads"] = {k: head(v) for k, v in redfin_urls.items()}
    for k, v in report["probes"]["redfin_heads"].items():
        print(f"  {k}: {v.get('status')} len={v.get('content_length')} lm={v.get('last_modified')}", flush=True)

    # Stream first Austin/Seattle metro row if metro HEAD is 200 and size is large
    metro_head = report["probes"]["redfin_heads"]["metro"]
    if metro_head.get("status") == 200:
        print("=== Stream first metro match (Austin/Seattle) ===", flush=True)
        def metro_match(row):
            region = (row.get("REGION") or row.get("CITY") or "").lower()
            return "austin" in region or "seattle" in region
        report["probes"]["redfin_metro_stream"] = stream_gzip_first_match(
            redfin_urls["metro"],
            OUT / "redfin_metro_first_match.json",
            metro_match,
            max_read=6_000_000,
            timeout=40,
        )
        m = report["probes"]["redfin_metro_stream"]
        print(
            f"  status={m.get('status')} scanned={m.get('scanned_rows')} "
            f"match={bool(m.get('match'))} bytes_read={m.get('bytes_read')} err={m.get('error')}",
            flush=True,
        )
    else:
        report["probes"]["redfin_metro_stream"] = {"skipped": True, "reason": metro_head}

    # Zillow
    zillow = {
        "inventory_week": "https://files.zillowstatic.com/research/public_csvs/invt_fs/Metro_invt_fs_uc_sfrcondo_sm_week.csv",
        "dom_week": "https://files.zillowstatic.com/research/public_csvs/mean_doz_pending/Metro_mean_doz_pending_uc_sfrcondo_sm_week.csv",
        "zhvi_city": "https://files.zillowstatic.com/research/public_csvs/zhvi/City_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
        "zhvi_metro": "https://files.zillowstatic.com/research/public_csvs/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
    }
    print("=== HEAD + download Zillow ===", flush=True)
    report["probes"]["zillow_heads"] = {k: head(v) for k, v in zillow.items()}
    for k, v in report["probes"]["zillow_heads"].items():
        print(f"  {k}: {v.get('status')} len={v.get('content_length')} lm={v.get('last_modified')}", flush=True)

    inv_path = OUT / "Metro_invt_fs_uc_sfrcondo_sm_week.csv"
    dom_path = OUT / "Metro_mean_doz_pending_uc_sfrcondo_sm_week.csv"
    report["probes"]["zillow_dl_inventory"] = download(zillow["inventory_week"], inv_path, timeout=60)
    report["probes"]["zillow_dl_dom"] = download(zillow["dom_week"], dom_path, timeout=45)
    print(f"  inv download: {report['probes']['zillow_dl_inventory']}", flush=True)
    print(f"  dom download: {report['probes']['zillow_dl_dom']}", flush=True)

    targets = ["United States", "Austin, TX", "Seattle, WA"]
    if inv_path.exists() and inv_path.stat().st_size > 100:
        report["probes"]["zillow_inventory_parse"] = parse_zillow_wide(inv_path, targets)
        print("  inventory parse:", json.dumps(report["probes"]["zillow_inventory_parse"], indent=2)[:2000], flush=True)
    if dom_path.exists() and dom_path.stat().st_size > 100:
        report["probes"]["zillow_dom_parse"] = parse_zillow_wide(dom_path, targets)
        print("  dom parse:", json.dumps(report["probes"]["zillow_dom_parse"], indent=2)[:2000], flush=True)

    # FRED
    print("=== FRED ===", flush=True)
    fred_m = OUT / "MORTGAGE30US.csv"
    fred_sp = OUT / "SP500.csv"
    report["probes"]["fred_mortgage_dl"] = download(
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US", fred_m, timeout=30
    )
    print("  mortgage:", report["probes"]["fred_mortgage_dl"], flush=True)
    if fred_m.exists() and fred_m.stat().st_size > 50:
        report["probes"]["fred_mortgage_parse"] = parse_fred_tail(fred_m, 5)
        print("  mortgage last:", report["probes"]["fred_mortgage_parse"]["last_n"], flush=True)

    report["probes"]["fred_sp500_dl"] = download(
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500", fred_sp, timeout=20
    )
    print("  sp500:", report["probes"]["fred_sp500_dl"], flush=True)
    if fred_sp.exists() and fred_sp.stat().st_size > 50:
        report["probes"]["fred_sp500_parse"] = parse_fred_tail(fred_sp, 5)

    # Yahoo
    print("=== Yahoo ===", flush=True)
    for sym, fname in [("%5EGSPC", "yahoo_gspc.json"), ("%5EIXIC", "yahoo_ixic.json")]:
        dest = OUT / fname
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1wk&range=2y"
        report["probes"][f"yahoo_{fname}_dl"] = download(url, dest, timeout=25)
        print(f"  {fname}:", report["probes"][f"yahoo_{fname}_dl"], flush=True)
        if dest.exists() and dest.stat().st_size > 50:
            try:
                parsed = parse_yahoo(dest)
                report["probes"][f"yahoo_{fname}_parse"] = parsed
                print("   parse:", parsed, flush=True)
            except Exception as e:
                report["probes"][f"yahoo_{fname}_parse"] = {"error": repr(e)}
                print("   parse error:", e, flush=True)

    # Census gazetteer
    print("=== Census gazetteer HEAD ===", flush=True)
    census_urls = [
        "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip",
        "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.txt",
    ]
    report["probes"]["census_heads"] = [head(u) for u in census_urls]
    for v in report["probes"]["census_heads"]:
        print(f"  {v.get('status')} {v.get('content_length')} {v.get('last_modified')} {v.get('url')}", flush=True)
    # Download if small
    for u, info in zip(census_urls, report["probes"]["census_heads"]):
        if info.get("status") == 200:
            cl = int(info.get("content_length") or 0)
            if 0 < cl < 5_000_000:
                dest = OUT / Path(u).name
                report["probes"]["census_dl"] = download(u, dest, timeout=40)
                print("  census dl:", report["probes"]["census_dl"], flush=True)
                break

    # Confirm no unauthenticated listing APIs
    print("=== Listing API unauth probes ===", flush=True)
    listing_probes = {
        "rentcast_sale": "https://api.rentcast.io/v1/listings/sale?city=Austin&state=TX&limit=1",
        "attom_prop": "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/basicprofile?address1=123%20Main",
        "bridge_v2": "https://api.bridgedataoutput.com/api/v2/test/listings?limit=1",
        "rapid_realty": "https://realty-in-us.p.rapidapi.com/properties/v3/list",
        "compass_www": "https://www.compass.com/robots.txt",
        "compass_api": "https://api.compass.com/",
        "stooq": "https://stooq.com/q/d/l/?s=^spx&i=w",
    }
    report["probes"]["listing_unauth"] = {}
    for k, url in listing_probes.items():
        info = head(url)
        # also try GET for a few that might differ
        if k in ("rentcast_sale", "stooq", "compass_api"):
            dest = OUT / f"unauth_{k}.bin"
            info["get"] = download(url, dest, timeout=15, max_bytes=8000)
        report["probes"]["listing_unauth"][k] = info
        print(f"  {k}: {info.get('status')} {info.get('error')}", flush=True)

    RESULTS.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("WROTE", RESULTS, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
