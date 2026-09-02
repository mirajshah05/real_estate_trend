"""Two-clock freshness: file Last-Modified vs observation as-of."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from realtykit.analysis.constants import AGING_HOURS, FRESH_HOURS, LIVE_HOURS
from realtykit.log import utc_iso, utc_now
from realtykit.models.freshness import FreshnessBlock, FreshnessStatus, SourceFreshness
from realtykit.store.sources import list_sources

_STATUS_RANK = {
    "live": 0,
    "fresh": 1,
    "aging": 2,
    "by_design_monthly": 3,
    "stale": 4,
    "unavailable": 5,
}


def parse_http_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def hours_since(value: str | datetime | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        if len(value) == 10 and value[4] == "-":
            try:
                dt = datetime.fromisoformat(value).replace(hour=23, minute=59, tzinfo=UTC)
            except ValueError:
                return None
        else:
            dt = parse_http_date(value)
            if dt is None:
                return None
    else:
        dt = value if value.tzinfo else value.replace(tzinfo=UTC)
    return max(0.0, (utc_now() - dt).total_seconds() / 3600.0)


def classify(
    *,
    observation_as_of: str | None,
    cadence: str,
    http_last_modified: str | None = None,
    forced: FreshnessStatus | None = None,
) -> tuple[FreshnessStatus, float | None]:
    if forced:
        return forced, hours_since(observation_as_of)
    if cadence == "monthly" and observation_as_of:
        return "by_design_monthly", hours_since(observation_as_of)
    obs_hours = hours_since(observation_as_of)
    if obs_hours is None:
        file_hours = hours_since(http_last_modified)
        if file_hours is None:
            return "unavailable", None
        if file_hours > AGING_HOURS:
            return "stale", file_hours
        return "aging", file_hours
    if cadence == "daily" and obs_hours <= LIVE_HOURS:
        return "live", obs_hours
    if obs_hours <= FRESH_HOURS:
        return "fresh", obs_hours
    if obs_hours <= AGING_HOURS:
        return "aging", obs_hours
    return "stale", obs_hours


def source_block(row: dict) -> SourceFreshness:
    cadence = row.get("cadence") or "unknown"
    forced: FreshnessStatus | None = None
    stored = row.get("freshness")
    if stored in {"unavailable", "by_design_monthly", "stale"}:
        forced = stored  # type: ignore[assignment]
    status, hours = classify(
        observation_as_of=row.get("observation_as_of"),
        cadence=cadence,
        http_last_modified=row.get("http_last_modified"),
        forced=forced,
    )
    stale = status in {"stale", "unavailable", "aging"}
    # aging is observation-late but not painted live; treat as stale for the 7-day SLA bit
    if status == "aging":
        stale = True
    return SourceFreshness(
        source=row.get("source_id") or row.get("source") or "",
        provider=row.get("provider") or "",
        dataset=row.get("dataset") or "",
        observation_as_of=row.get("observation_as_of"),
        http_last_modified=row.get("http_last_modified"),
        stale=stale,
        freshness_hours=round(hours, 1) if hours is not None else None,
        cadence=cadence,
        note=row.get("note") or "",
        status=status,
        fetched_at=row.get("fetched_at"),
    )


def worst(statuses: list[FreshnessStatus]) -> FreshnessStatus:
    if not statuses:
        return "unavailable"
    return max(statuses, key=lambda s: _STATUS_RANK.get(s, 99))


def build_freshness(
    rows: list[dict] | None = None,
    *,
    prefer_source: str | None = None,
) -> FreshnessBlock:
    rows = rows if rows is not None else list_sources()
    items = [source_block(r) for r in rows]
    primary = None
    if prefer_source:
        primary = next((i for i in items if i.source == prefer_source), None)
    if primary is None:
        for sid in (
            "zillow:inv_week_metro",
            "zillow:zhvi_metro",
            "yahoo:GSPC",
            "redfin:national_month",
        ):
            primary = next((i for i in items if i.source == sid), None)
            if primary:
                break
    if primary is None:
        primary = items[0] if items else SourceFreshness(source="none", provider="none")
    # Stubs (Compass, no-key RentCast) and Census geography do not set the banner.
    skip = {"census", "compass", "government"}
    if prefer_source:
        relevant = [i.status for i in items if i.source == prefer_source]
    else:
        relevant = [i.status for i in items if i.provider not in skip and i.status != "unavailable"]
    overall = worst(relevant)
    return FreshnessBlock(
        computed_at=utc_iso(),
        overall=overall,
        source=primary.source,
        observation_as_of=primary.observation_as_of,
        http_last_modified=primary.http_last_modified,
        stale=primary.stale or overall in {"stale", "unavailable"},
        freshness_hours=primary.freshness_hours,
        cadence=primary.cadence,
        note=primary.note,
        sources=items,
    )


def honesty_banner() -> str:
    rows = list_sources()
    by_provider = {row.get("source_id"): row for row in rows}
    bits: list[str] = []
    housing = by_provider.get("zillow:inv_week_metro")
    if housing and housing.get("observation_as_of"):
        bits.append(f"Housing weeks through {housing['observation_as_of']}")
    stocks = by_provider.get("yahoo:GSPC")
    if stocks and stocks.get("observation_as_of"):
        bits.append(f"stocks through {stocks['observation_as_of']}")
    redfin = by_provider.get("redfin:national_month")
    if redfin and redfin.get("observation_as_of"):
        bits.append(f"Redfin national through {redfin['observation_as_of'][:7]}")
    mortgage = by_provider.get("fred:MORTGAGE30US")
    if mortgage and mortgage.get("observation_as_of"):
        bits.append(f"mortgage rates through {mortgage['observation_as_of']}")
    else:
        bits.append("mortgage rates unavailable")
    return "; ".join(bits) + "."
