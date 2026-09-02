"""52-week dip detectors. Not a buy signal."""

from __future__ import annotations

from realtykit.analysis.constants import DIP_DRAWDOWN_FROM_HIGH, DIP_PCT_ABOVE_52W_LOW


def dip_metrics(
    last: float,
    low_52w: float,
    high_52w: float,
    *,
    pct_above_low_thresh: float = DIP_PCT_ABOVE_52W_LOW,
    drawdown_thresh: float = DIP_DRAWDOWN_FROM_HIGH,
) -> dict:
    pct_above_low = None if low_52w in (None, 0) else (last - low_52w) / low_52w
    drawdown = None if high_52w in (None, 0) else (last - high_52w) / high_52w
    near_low = pct_above_low is not None and pct_above_low <= pct_above_low_thresh
    deep_dd = drawdown is not None and drawdown <= drawdown_thresh
    return {
        "last": last,
        "low_52w": low_52w,
        "high_52w": high_52w,
        "pct_above_52w_low": pct_above_low,
        "drawdown_52w": drawdown,
        "dip": bool(near_low or deep_dd),
        "dip_reasons": [
            *(["near_52w_low"] if near_low else []),
            *(["drawdown_from_52w_high"] if deep_dd else []),
        ],
    }


def trailing_52w(closes: list[tuple[str, float]], last_n: int = 52) -> tuple[float, float, float]:
    """Return (last, low, high) from the trailing window of weekly or daily closes."""
    window = [v for _, v in closes[-last_n:] if v is not None]
    if not window:
        raise ValueError("no closes")
    return window[-1], min(window), max(window)


def historical_dips(closes: list[tuple[str, float]], *, lookback_days: int = 365) -> list[dict]:
    """Return the first weekly observation of each trailing-52-week dip run."""
    if len(closes) < 2:
        return []
    points = closes[-max(2, lookback_days // 7) :]
    events: list[dict] = []
    was_dip = False
    for i, (ts, close) in enumerate(points):
        window = [value for _, value in points[max(0, i - 51) : i + 1]]
        if len(window) < 4:
            continue
        metrics = dip_metrics(close, min(window), max(window))
        is_dip = bool(metrics["dip"])
        if is_dip and not was_dip:
            events.append(
                {
                    "t": ts,
                    "close": close,
                    "kind": "historical",
                    "from_peak": metrics["drawdown_52w"],
                    "pct_above_52w_low": metrics["pct_above_52w_low"],
                }
            )
        was_dip = is_dip
    return events
