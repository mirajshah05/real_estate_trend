"""Shared fixtures for RealtyKit analysis and API contract tests.

Tests stay offline: no live HTTP. The repo root is put on sys.path so
`import realtykit` works once Agent A lands the package.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Research compile clock from docs/research/03-data-extraction.md
NOW_UTC = datetime(2026, 8, 31, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def now_utc(monkeypatch: pytest.MonkeyPatch) -> datetime:
    # Keep freshness contract tests pinned to the research compile clock.  The
    # production classifier reads its clock internally, so passing ``now`` via
    # a compatibility helper alone cannot make these fixtures deterministic.
    from realtykit import freshness

    monkeypatch.setattr(freshness, "utc_now", lambda: NOW_UTC)
    return NOW_UTC


@pytest.fixture
def source_rows() -> dict:
    return json.loads((FIXTURES / "source_rows.json").read_text(encoding="utf-8"))


@pytest.fixture
def listings_bundle() -> dict:
    return json.loads((FIXTURES / "listings.json").read_text(encoding="utf-8"))


@pytest.fixture
def series_bundle() -> dict:
    return json.loads((FIXTURES / "series.json").read_text(encoding="utf-8"))


@pytest.fixture
def dip_cases() -> dict:
    return json.loads((FIXTURES / "equity_bars.json").read_text(encoding="utf-8"))


@pytest.fixture
def metro_rows() -> list[dict]:
    import csv

    path = FIXTURES / "metro_values.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
