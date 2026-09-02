from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from realtykit.analysis.dips import dip_metrics, historical_dips, trailing_52w
from realtykit.api.deps import ensure_store
from realtykit.api.schemas import STOCK_SYMBOLS, StockLast, StocksDipsResponse
from realtykit.freshness import build_freshness
from realtykit.store.facts import macro_series

router = APIRouter()

_ALIAS = {
    "^GSPC": "GSPC",
    "^IXIC": "IXIC",
    "^DJI": "DJI",
    "GSPC": "GSPC",
    "IXIC": "IXIC",
    "DJI": "DJI",
}


def _scope_fields(series: list[tuple[str, float]], lookback_days: int) -> dict:
    event_points = series[-max(2, lookback_days // 7) :] if series else []
    return {
        "lookback_days": lookback_days,
        "threshold_window_weeks": 52,
        "event_window_start": event_points[0][0] if event_points else None,
        "history_start": series[0][0] if series else None,
        "history_end": series[-1][0] if series else None,
        "history_points": len(series),
        "note": (
            "Recent-event scanner only: events are limited to the requested "
            f"{lookback_days}-day lookback and evaluated against trailing 52-week "
            "highs and lows. This is not an all-history crisis list; the 2008 "
            "financial crisis is outside the loaded range."
        ),
    }


@router.get("/stocks/dips", response_model=StocksDipsResponse)
def stock_dips(
    symbol: str = Query(default="^GSPC"),
    lookback_days: int = Query(default=365, ge=30, le=4000),
    _ok: None = Depends(ensure_store),
) -> StocksDipsResponse:
    if symbol not in STOCK_SYMBOLS:
        symbol = "^GSPC"
    series_id = _ALIAS.get(symbol, "GSPC")
    weekly = macro_series(series_id)
    daily = macro_series(f"{series_id}_D")
    closes = daily or weekly
    analysis_series = weekly or closes
    scope = _scope_fields(analysis_series, lookback_days)
    if not closes:
        return StocksDipsResponse(
            freshness=build_freshness(prefer_source=f"yahoo:{series_id}"),
            symbol=symbol,
            last=StockLast(),
            dips=[],
            **scope,
        )
    last, low, high = trailing_52w(analysis_series, last_n=min(52, len(analysis_series)))
    if daily:
        last = daily[-1][1]
    metrics = dip_metrics(last, low, high)
    last_t = (daily or weekly)[-1][0]
    dips = historical_dips(analysis_series, lookback_days=lookback_days)
    if metrics["dip"]:
        current = {
            "t": last_t,
            "close": last,
            "kind": "current",
            "from_peak": metrics["drawdown_52w"],
            "pct_above_52w_low": metrics["pct_above_52w_low"],
        }
        if not dips or dips[-1].get("t") != last_t:
            dips.append(current)
    return StocksDipsResponse(
        freshness=build_freshness(prefer_source=f"yahoo:{series_id}"),
        symbol=symbol,
        last=StockLast(
            t=last_t,
            close=last,
            pct_above_52w_low=metrics["pct_above_52w_low"],
            drawdown_52w=metrics["drawdown_52w"],
            dip=metrics["dip"],
        ),
        dips=dips,
        **scope,
    )
