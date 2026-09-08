from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from realtykit.settings import Settings
from realtykit.store.provider_usage import (
    ProviderQuotaExceeded,
    record_attempt,
    record_result,
    usage_snapshot,
)


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        REALTYKIT_DATA_DIR=path,
        RENTCAST_API_KEY="test-only",
        RENTCAST_MONTHLY_LIMIT=2,
        RENTCAST_WARNING_AT=1,
    )


def test_usage_is_persistent_and_reserves_atomically(tmp_path: Path):
    settings = _settings(tmp_path)
    record_attempt("rentcast", settings)
    reserved = usage_snapshot("rentcast", settings)
    assert reserved["reserved_requests"] == 1
    assert reserved["remaining"] == 1

    record_result("rentcast", 503, successful=False, settings=settings)
    failed = usage_snapshot("rentcast", settings)
    assert failed["reserved_requests"] == 0
    assert failed["attempted_requests"] == 1
    assert failed["remaining"] == 1

    # A newly constructed Settings object uses the same offline SQLite ledger,
    # and the failed call still consumes one of the two allowed attempts.
    restarted = _settings(tmp_path)
    record_attempt("rentcast", restarted)
    record_result("rentcast", 200, successful=True, settings=restarted)

    final = usage_snapshot("rentcast", restarted)
    assert final["attempted_requests"] == 2
    assert final["successful_requests"] == 1
    assert final["remaining"] == 0
    assert final["alert"]
    with pytest.raises(ProviderQuotaExceeded):
        record_attempt("rentcast", restarted)
    assert (tmp_path / "realtykit.db").stat().st_mode & 0o777 == 0o600


def test_environment_cannot_raise_rentcast_hard_cap(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        REALTYKIT_DATA_DIR=tmp_path,
        RENTCAST_API_KEY="test-only",
        RENTCAST_MONTHLY_LIMIT=500,
        RENTCAST_WARNING_AT=450,
    )
    for _ in range(40):
        record_attempt("rentcast", settings)
        record_result("rentcast", 503, successful=False, settings=settings)

    usage = usage_snapshot("rentcast", settings)
    assert usage["limit"] == 40
    assert usage["warning_at"] == 32
    assert usage["attempted_requests"] == 40
    assert usage["successful_requests"] == 0
    assert usage["remaining"] == 0
    with pytest.raises(ProviderQuotaExceeded):
        record_attempt("rentcast", settings)


def test_concurrent_process_style_reservations_stop_at_hard_cap(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        REALTYKIT_DATA_DIR=tmp_path,
        RENTCAST_API_KEY="test-only",
        RENTCAST_MONTHLY_LIMIT=500,
    )
    usage_snapshot("rentcast", settings)  # Initialize the database before contention.

    def reserve_one(_index: int) -> bool:
        try:
            record_attempt("rentcast", settings)
            return True
        except ProviderQuotaExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        allowed = list(pool.map(reserve_one, range(48)))

    assert sum(allowed) == 40
    usage = usage_snapshot("rentcast", settings)
    assert usage["attempted_requests"] == 40
    assert usage["remaining"] == 0
