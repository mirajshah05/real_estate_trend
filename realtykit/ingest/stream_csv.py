"""Wide Zillow CSV melt. Stream rows; do not hold a giant matrix."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

ID_COLS = ("RegionID", "SizeRank", "RegionName", "RegionType", "StateName")


def date_columns(fieldnames: list[str]) -> list[str]:
    return [c for c in fieldnames if c[:4].isdigit()]


def melt_wide_csv(
    path: Path,
    *,
    min_period: str | None = None,
    latest_only: bool = False,
) -> Iterator[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return
        dates = date_columns(list(reader.fieldnames))
        if min_period:
            dates = [d for d in dates if d >= min_period]
        if latest_only and dates:
            dates = [dates[-1]]
        for row in reader:
            for period in dates:
                raw = row.get(period)
                if raw in (None, ""):
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    continue
                yield {
                    "region_id": row.get("RegionID") or "",
                    "size_rank": row.get("SizeRank") or "",
                    "name": row.get("RegionName") or "",
                    "region_type": row.get("RegionType") or "",
                    "state": row.get("StateName") or "",
                    "period_end": period,
                    "value": value,
                }


def latest_week(path: Path) -> str | None:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
    if not header:
        return None
    dates = date_columns(header)
    return dates[-1] if dates else None
