from __future__ import annotations

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
    assert usage_snapshot("rentcast", settings)["reserved_requests"] == 0

    for _ in range(2):
        record_attempt("rentcast", settings)
        record_result("rentcast", 200, successful=True, settings=settings)

    final = usage_snapshot("rentcast", settings)
    assert final["successful_requests"] == 2
    assert final["remaining"] == 0
    assert final["alert"]
    with pytest.raises(ProviderQuotaExceeded):
        record_attempt("rentcast", settings)
    assert (tmp_path / "realtykit.db").stat().st_mode & 0o777 == 0o600
