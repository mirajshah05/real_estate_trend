"""Stock dip contract: ≤5% above 52w low or ≤−20% from 52w high."""

from __future__ import annotations

import pytest

from tests.contract import (
    DIP_DRAWDOWN_MAX,
    DIP_NEAR_LOW_MAX,
    constants_mod,
    dip_fn,
    field,
    invoke_dip,
    is_dip,
)


def test_dip_threshold_constants():
    const = constants_mod()
    near = getattr(const, "DIP_NEAR_LOW_MAX", None) or getattr(
        const, "DIP_NEAR_LOW_PCT", None
    ) or getattr(const, "DIP_PCT_ABOVE_52W_LOW", None)
    draw = getattr(const, "DIP_DRAWDOWN_MAX", None) or getattr(
        const, "DIP_DRAWDOWN_PCT", None
    ) or getattr(const, "DIP_DRAWDOWN_FROM_HIGH", None)
    if near is not None:
        assert float(near) == pytest.approx(DIP_NEAR_LOW_MAX)
    if draw is not None:
        assert float(draw) == pytest.approx(DIP_DRAWDOWN_MAX)


def test_flag_when_within_5pct_of_52w_low(dip_cases):
    dip_fn()
    case = dip_cases["near_low"]
    result = invoke_dip(
        price=case["price"],
        low_52w=case["low_52w"],
        high_52w=case["high_52w"],
    )
    assert is_dip(result) is True
    pct = field(result, "pct_above_52w_low", "pct_above_low")
    if pct is not None:
        assert float(pct) == pytest.approx(0.05, abs=1e-9)
        assert float(pct) <= DIP_NEAR_LOW_MAX


def test_flag_when_drawdown_is_minus_20pct_from_52w_high(dip_cases):
    dip_fn()
    case = dip_cases["drawdown"]
    result = invoke_dip(
        price=case["price"],
        low_52w=case["low_52w"],
        high_52w=case["high_52w"],
    )
    assert is_dip(result) is True
    dd = field(
        result,
        "drawdown_from_52w_high",
        "drawdown_52w",
        "from_peak",
        "drawdown",
    )
    if dd is not None:
        assert float(dd) == pytest.approx(DIP_DRAWDOWN_MAX, abs=1e-9)
        assert float(dd) <= DIP_DRAWDOWN_MAX


def test_no_flag_when_neither_threshold_hits(dip_cases):
    dip_fn()
    case = dip_cases["neither"]
    result = invoke_dip(
        price=case["price"],
        low_52w=case["low_52w"],
        high_52w=case["high_52w"],
    )
    assert is_dip(result) is False
