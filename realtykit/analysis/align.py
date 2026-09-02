"""Align weekly series without interpolation."""

from __future__ import annotations

from datetime import date, timedelta
from math import log


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def iso_week_key(value: str | date) -> date:
    """Map any date to that ISO week's Friday (housing / equity join key)."""
    d = value if isinstance(value, date) else parse_date(value)
    monday = d - timedelta(days=d.weekday())
    return monday + timedelta(days=4)


def pct_change(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev in (None, 0):
        return None
    return (cur - prev) / prev


def log_return(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or cur <= 0 or prev <= 0:
        return None
    return log(cur) - log(prev)


def to_points(rows: list[tuple[str, float]]) -> dict[date, float]:
    out: dict[date, float] = {}
    for ts, value in rows:
        if value is None:
            continue
        out[iso_week_key(ts)] = float(value)
    return out


def align_weekly(*series: list[tuple[str, float]]) -> list[tuple[date, list[float]]]:
    """Inner-join series on ISO-week Friday. Missing values are omitted (no fill)."""
    maps = [to_points(s) for s in series]
    if not maps:
        return []
    keys = set(maps[0])
    for m in maps[1:]:
        keys &= set(m)
    aligned: list[tuple[date, list[float]]] = []
    for key in sorted(keys):
        aligned.append((key, [m[key] for m in maps]))
    return aligned


def differenced_returns(points: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Week-over-week log returns. First observation dropped."""
    ordered = sorted((parse_date(t), v) for t, v in points if v is not None and v > 0)
    out: list[tuple[str, float]] = []
    for i in range(1, len(ordered)):
        ret = log_return(ordered[i][1], ordered[i - 1][1])
        if ret is not None:
            out.append((ordered[i][0].isoformat(), ret))
    return out


def first_differences(points: list[tuple[str, float]]) -> list[tuple[str, float]]:
    ordered = sorted((parse_date(t), v) for t, v in points if v is not None)
    out: list[tuple[str, float]] = []
    for i in range(1, len(ordered)):
        out.append((ordered[i][0].isoformat(), ordered[i][1] - ordered[i - 1][1]))
    return out
