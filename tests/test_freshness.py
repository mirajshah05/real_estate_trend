"""Freshness contract: dual clocks, 168h listing/city SLA, reject missing as_of.

Primary 7-day SLA is observation_as_of, not http_last_modified
(docs/research/00-orchestration.md §7, 03-data-extraction.md).
"""

from __future__ import annotations

import pytest

from tests.contract import (
    STALE_HOURS,
    constants_mod,
    field,
    freshness_fn,
    invoke_freshness,
    invoke_listing,
    is_stale,
    listing_validator,
    status_of,
)


def _status_text(result) -> str:
    return (status_of(result) or "").lower()


def test_stale_hours_constant_is_168():
    const = constants_mod()
    hours = (
        getattr(const, "STALE_HOURS", None)
        or getattr(const, "LISTING_STALE_HOURS", None)
        or getattr(const, "LISTING_SLA_HOURS", None)
        or getattr(const, "FRESH_HOURS", None)
    )
    if hours is not None:
        assert float(hours) == STALE_HOURS


def test_listing_stale_when_observation_over_168h(source_rows, now_utc):
    freshness_fn()
    result = invoke_freshness(source_rows["stale_listing"], now_utc)
    # File clock is ~1h old; observation is 11 days. Observation wins.
    assert is_stale(result) is True


def test_city_stale_when_observation_over_168h(source_rows, now_utc):
    freshness_fn()
    result = invoke_freshness(source_rows["stale_city"], now_utc)
    assert is_stale(result) is True


def test_recent_listing_is_not_stale(source_rows, now_utc):
    freshness_fn()
    result = invoke_freshness(source_rows["fresh_listing"], now_utc)
    assert is_stale(result) is False
    assert _status_text(result) not in {"stale"}


def test_dual_clock_file_fresh_does_not_save_stale_observation(source_rows, now_utc):
    """http_last_modified must not be treated as as_of."""
    freshness_fn()
    row = source_rows["stale_listing"]
    result = invoke_freshness(row, now_utc)
    obs = field(result, "observation_as_of", "as_of")
    http_lm = field(result, "http_last_modified")
    if obs is not None:
        assert str(obs).startswith("2026-08-20")
    if http_lm is not None:
        assert "2026-08-31" in str(http_lm)
    assert is_stale(result) is True


def test_zillow_weekly_file_fresh_observation_stale_allowed(source_rows, now_utc):
    """Weekly file LM 2026-08-25 + week 2026-08-15 is a valid dual-clock row."""
    freshness_fn()
    row = source_rows["zillow_weekly_dual"]
    result = invoke_freshness(row, now_utc)
    assert result is not None
    status = _status_text(result)
    assert status not in {"live", "unavailable"}
    # Observation (~16d) is stale; file (~6d) is fresh — both clocks may appear.
    obs = field(result, "observation_as_of", "as_of")
    http_lm = field(result, "http_last_modified")
    if obs is not None:
        assert "2026-08-15" in str(obs)
    if http_lm is not None:
        assert "2026-08-25" in str(http_lm)


def test_zhvi_monthly_is_by_design_monthly_not_live(source_rows, now_utc):
    freshness_fn()
    result = invoke_freshness(source_rows["zhvi_monthly"], now_utc)
    status = _status_text(result)
    assert status == "by_design_monthly"
    assert status not in {"live", "fresh"}


def test_reject_listing_without_as_of():
    validator = listing_validator()
    payload = {
        "listing_id": "missing-as-of",
        "geo_id": "metro:austin",
        "price": 400000,
        "dom": 12,
        "source": "fixture",
    }
    with pytest.raises(Exception) as exc_info:
        invoke_listing(validator, payload)
    # Pydantic ValidationError subclasses ValueError.
    message = str(exc_info.value).lower()
    name = type(exc_info.value).__name__.lower()
    assert (
        "as_of" in message
        or "observation_as_of" in message
        or "required" in message
        or "validation" in name
    )


def test_listing_with_as_of_is_accepted():
    validator = listing_validator()
    payload = {
        "listing_id": "has-as-of",
        "geo_id": "metro:austin",
        "price": 400000,
        "dom": 12,
        "as_of": "2026-08-31",
        "observation_as_of": "2026-08-31",
        "source": "fixture",
    }
    result = invoke_listing(validator, payload)
    assert result is not None
