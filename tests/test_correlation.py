"""Correlation contract: Pearson, n<12 → insufficient_history, no causation copy."""

from __future__ import annotations

import re
import statistics

import pytest

from tests.contract import (
    MIN_CORRELATION_N,
    collect_messages,
    constants_mod,
    field,
    invoke_correlate,
    invoke_pearson,
    pearson_fn,
    status_of,
)


def test_min_correlation_n_is_12():
    const = constants_mod()
    n = getattr(const, "MIN_CORRELATION_N", None) or getattr(const, "CORRELATION_MIN_N", None)
    if n is not None:
        assert int(n) == MIN_CORRELATION_N


def test_pearson_perfect_positive():
    pearson_fn()
    xs = [float(i) for i in range(1, 13)]
    ys = [2.0 * v for v in xs]
    assert invoke_pearson(xs, ys) == pytest.approx(1.0)


def test_pearson_perfect_negative():
    pearson_fn()
    xs = [float(i) for i in range(1, 13)]
    ys = [-v for v in xs]
    assert invoke_pearson(xs, ys) == pytest.approx(-1.0)


def test_pearson_matches_stdlib_on_fixture_vectors(series_bundle):
    pearson_fn()
    xs = [float(v) for v in series_bundle["housing"]]
    ys = [float(v) for v in series_bundle["equity"]]
    expected = statistics.correlation(xs, ys)
    assert invoke_pearson(xs, ys) == pytest.approx(expected, abs=1e-12)


def test_insufficient_history_when_n_under_12(series_bundle):
    xs = [float(v) for v in series_bundle["short_housing"]]
    ys = [float(v) for v in series_bundle["short_equity"]]
    assert len(xs) < MIN_CORRELATION_N
    try:
        result = invoke_correlate(xs, ys)
    except Exception as exc:  # noqa: BLE001 - compatibility contract accepts multiple implementations
        blob = f"{type(exc).__name__} {exc}".lower()
        assert "insufficient_history" in blob
        return
    status = (status_of(result) or "").lower()
    reason = str(field(result, "reason", "code", "error") or "").lower()
    n = field(result, "n")
    if n is not None:
        assert int(n) < MIN_CORRELATION_N
    assert status == "insufficient_history" or reason == "insufficient_history"


def test_sufficient_history_returns_coefficient(series_bundle):
    xs = [float(v) for v in series_bundle["housing"]]
    ys = [float(v) for v in series_bundle["equity"]]
    assert len(xs) >= MIN_CORRELATION_N
    result = invoke_correlate(xs, ys)
    status = (status_of(result) or "").lower()
    if status:
        assert status != "insufficient_history"
    coef = field(result, "pearson", "r", "value")
    if coef is None and isinstance(result, (int, float)):
        coef = result
    if coef is None:
        pairs = field(result, "pairs") or []
        if pairs:
            coef = field(pairs[0], "pearson", "r")
    assert coef is not None
    assert float(coef) == pytest.approx(statistics.correlation(xs, ys), abs=1e-9)


def test_no_causation_in_returned_copy_if_message_exists(series_bundle):
    xs = [float(v) for v in series_bundle["housing"]]
    ys = [float(v) for v in series_bundle["equity"]]
    result = invoke_correlate(xs, ys)
    messages = collect_messages(result)
    causal = re.compile(r"\b(causes|caused|causal effect|therefore prices)\b")
    for text in messages:
        lower = text.lower()
        if "causation" in lower:
            assert "not causation" in lower or "correlation is not" in lower
        assert causal.search(lower) is None
