"""Pearson correlation on aligned weekly series. No causation copy."""

from __future__ import annotations

import statistics

from realtykit.analysis.align import align_weekly, differenced_returns, first_differences
from realtykit.analysis.constants import DISCLAIMER, MIN_CORRELATION_N
from realtykit.models.analysis import CorrelationPair, CorrelationResult


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(ys) < 2 or len(xs) != len(ys):
        return None
    if statistics.pstdev(xs) == 0 or statistics.pstdev(ys) == 0:
        return None
    return statistics.correlation(xs, ys)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson r on two equal-length numeric vectors (levels, not returns)."""
    return _pearson(list(xs), list(ys))


def pearson_pairs(
    housing: list[tuple[str, float]],
    equity: list[tuple[str, float]] | None,
    mortgage: list[tuple[str, float]] | None,
    *,
    min_n: int = MIN_CORRELATION_N,
) -> CorrelationResult:
    """Correlate housing returns vs ^GSPC returns vs mortgage first differences.

    Housing and equity use log returns. Mortgage uses level changes (already
    percent points). Observations with a missing pair are dropped, not filled.
    """
    housing_r = differenced_returns(housing)
    equity_r = differenced_returns(equity) if equity else []
    mort_d = first_differences(mortgage) if mortgage else []

    pairs: list[CorrelationPair] = []
    ns: list[int] = []

    def add(name_a: str, name_b: str, a: list[tuple[str, float]], b: list[tuple[str, float]]) -> None:
        if not a or not b:
            pairs.append(
                CorrelationPair(a=name_a, b=name_b, n=0, note="series_unavailable")
            )
            return
        aligned = align_weekly(a, b)
        n = len(aligned)
        ns.append(n)
        if n < min_n:
            pairs.append(
                CorrelationPair(
                    a=name_a,
                    b=name_b,
                    n=n,
                    note="insufficient_history",
                )
            )
            return
        xs = [row[1][0] for row in aligned]
        ys = [row[1][1] for row in aligned]
        pairs.append(
            CorrelationPair(a=name_a, b=name_b, pearson=_pearson(xs, ys), n=n)
        )

    add("housing_return", "gspc_return", housing_r, equity_r)
    add("housing_return", "mortgage_change", housing_r, mort_d)
    add("gspc_return", "mortgage_change", equity_r, mort_d)

    usable = [p.n for p in pairs if p.pearson is not None]
    n = min(usable) if usable else (min(ns) if ns else 0)
    status = "ok" if usable else "insufficient_history"
    return CorrelationResult(n=n, status=status, pairs=pairs, disclaimer=DISCLAIMER)
