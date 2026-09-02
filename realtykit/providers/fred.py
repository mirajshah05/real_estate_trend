"""FRED MORTGAGE30US. Timeout 8s. Optional key. Last-good cache. Never block ingest."""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import UTC, datetime

import httpx

from realtykit.freshness import classify
from realtykit.ingest.http import FRED_TIMEOUT, CachedHttp, sha256_file, write_meta
from realtykit.log import log, utc_iso
from realtykit.providers.base import FetchOutcome
from realtykit.settings import Settings, get_settings
from realtykit.store.facts import upsert_macro
from realtykit.store.sources import upsert_source

CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
PMMS_URL = "https://www.freddiemac.com/pmms/docs/PMMS_history.csv"
API_URL = "https://api.stlouisfed.org/fred/series/observations"


def ingest(
    conn: sqlite3.Connection, settings: Settings | None = None, force: bool = False
) -> FetchOutcome:
    settings = settings or get_settings()
    http = CachedHttp(settings)
    fetched_at = utc_iso()
    dest = http.dest("fred/MORTGAGE30US.csv")
    last_modified = None
    etag = None
    digest = None
    size = dest.stat().st_size if dest.exists() else None
    text: str | None = None
    source_url = CSV_URL
    note_bits: list[str] = []

    if settings.has_fred_key:
        try:
            params = {
                "series_id": "MORTGAGE30US",
                "api_key": settings.fred_api_key,
                "file_type": "json",
                "sort_order": "asc",
            }
            with httpx.Client(
                timeout=FRED_TIMEOUT, headers={"User-Agent": settings.user_agent}
            ) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
            lines = ["DATE,MORTGAGE30US"]
            for obs in payload.get("observations") or []:
                val = obs.get("value")
                if val in (None, "."):
                    continue
                lines.append(f"{obs.get('date')},{val}")
            text = "\n".join(lines) + "\n"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            digest = sha256_file(dest)
            write_meta(
                dest,
                {
                    "url": API_URL,
                    "etag": None,
                    "last_modified": None,
                    "content_sha256": digest,
                    "bytes": dest.stat().st_size,
                    "fetched_at": utc_iso(),
                },
            )
            size = dest.stat().st_size
            note_bits.append("loaded via official FRED API using configured key")
        except Exception as exc:  # noqa: BLE001
            note_bits.append("API fail")
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            log("fred_api_failed", error_type=type(exc).__name__, status=status)

    if text is None:
        try:
            cached = http.get_cached(
                CSV_URL,
                "fred/MORTGAGE30US.csv",
                timeout=FRED_TIMEOUT,
                force=force,
                retries=2,
            )
            text = cached.path.read_text(encoding="utf-8")
            last_modified = cached.last_modified
            etag = cached.etag
            digest = cached.content_sha256
            size = cached.bytes
            fetched_at = cached.fetched_at
        except Exception as exc:  # noqa: BLE001
            note_bits.append(f"CSV timeout/fail ({exc})")
            log("fred_csv_failed", error=str(exc))

    if text is None:
        try:
            pmms = http.get_cached(
                PMMS_URL,
                "freddie/PMMS_history.csv",
                timeout=12.0,
                force=force,
                retries=2,
            )
            text = pmms.path.read_text(encoding="utf-8-sig")
            last_modified = pmms.last_modified
            etag = pmms.etag
            digest = pmms.content_sha256
            size = pmms.bytes
            fetched_at = pmms.fetched_at
            note_bits.append("loaded via official Freddie Mac PMMS file")
            source_url = PMMS_URL
        except Exception as exc:  # noqa: BLE001
            note_bits.append(f"Freddie Mac PMMS fail ({exc})")

    if text is None and dest.exists():
        text = dest.read_text(encoding="utf-8")
        note_bits.append("using last-good cache")

    if not text:
        out = FetchOutcome(
            source_id="fred:MORTGAGE30US",
            provider="fred",
            dataset="MORTGAGE30US",
            url=source_url,
            status="error",
            fetched_at=fetched_at,
            cadence="weekly",
            freshness="unavailable",
            note="Live fetch failed; no last-good cache. Housing ingest not blocked. "
            + " ".join(note_bits),
            http_last_modified=last_modified,
        )
        upsert_source(out.as_source_row(), conn)
        return out

    points: list[dict] = []
    latest = None
    reader = csv.DictReader(io.StringIO(text))
    value_key = None
    date_key = None
    if reader.fieldnames:
        date_key = next(
            (k for k in reader.fieldnames if k.strip().lower() in {"date", "week"}), None
        )
        value_key = next(
            (
                k
                for k in reader.fieldnames
                if k != date_key
                and "30" in k.lower()
                and ("yr" in k.lower() or "year" in k.lower())
            ),
            None,
        ) or next((k for k in reader.fieldnames if k != date_key), None)
    for row in reader:
        ts = row.get(date_key) if date_key else (row.get("DATE") or row.get("date"))
        raw = row.get(value_key) if value_key else None
        if not ts or raw in (None, "", "."):
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        latest = _normalise_date(ts)
        if latest is None:
            continue
        points.append(
            {
                "series_id": "MORTGAGE30US",
                "ts": latest,
                "value": value,
                "provider": "fred",
                "source_id": "fred:MORTGAGE30US",
            }
        )
    if points:
        upsert_macro(points, conn)
    status, _ = classify(
        observation_as_of=latest, cadence="weekly", http_last_modified=last_modified
    )
    out = FetchOutcome(
        source_id="fred:MORTGAGE30US",
        provider="fred",
        dataset="MORTGAGE30US",
        url=source_url,
        status="ok" if points else "error",
        fetched_at=fetched_at,
        cadence="weekly",
        observation_as_of=latest,
        http_last_modified=last_modified,
        etag=etag,
        content_sha256=digest,
        bytes=size,
        freshness=status if points else "unavailable",
        note="Freddie Mac 30-year mortgage survey. " + " ".join(note_bits),
        path=dest if dest.exists() else None,
        rows_upserted=len(points),
    )
    upsert_source(out.as_source_row(), conn)
    return out


def _normalise_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value[:10]).date().isoformat()
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None
