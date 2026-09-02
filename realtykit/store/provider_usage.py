"""Persistent provider request accounting and sanitized response caching."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from realtykit.log import utc_iso
from realtykit.settings import Settings, get_settings
from realtykit.store.db import connect


class ProviderQuotaExceeded(RuntimeError):
    """Raised before a request that would exceed the configured local cap."""


def _period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def usage_snapshot(provider: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    period = _period()
    conn = connect(settings)
    try:
        row = conn.execute(
            "SELECT * FROM provider_usage WHERE provider = ? AND period = ?",
            (provider, period),
        ).fetchone()
    finally:
        conn.close()
    successful = int(row["successful_requests"]) if row else 0
    attempted = int(row["attempted_requests"]) if row else 0
    reserved = int(row["reserved_requests"]) if row else 0
    limit = settings.rentcast_monthly_limit if provider == "rentcast" else None
    warning_at = settings.rentcast_warning_at if provider == "rentcast" else None
    remaining = max(0, limit - successful - reserved) if limit is not None else None
    alert = None
    if limit is not None and successful >= limit:
        alert = f"{provider.title()} local monthly cap reached; live requests are paused."
    elif warning_at is not None and successful >= warning_at:
        alert = f"{provider.title()} is nearing its local monthly cap ({successful}/{limit})."
    return {
        "provider": provider,
        "period": period,
        "attempted_requests": attempted,
        "successful_requests": successful,
        "reserved_requests": reserved,
        "limit": limit,
        "warning_at": warning_at,
        "remaining": remaining,
        "alert": alert,
        "tracked_since": row["tracked_since"] if row else None,
        "last_status": row["last_status"] if row else None,
        "external_usage_unknown": True,
    }


def record_attempt(provider: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    now = utc_iso()
    period = _period()
    conn = connect(settings)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT successful_requests, reserved_requests FROM provider_usage WHERE provider = ? AND period = ?",
            (provider, period),
        ).fetchone()
        successful = int(row["successful_requests"]) if row else 0
        reserved = int(row["reserved_requests"]) if row else 0
        limit = settings.rentcast_monthly_limit if provider == "rentcast" else None
        if limit is not None and successful + reserved >= limit:
            conn.rollback()
            raise ProviderQuotaExceeded(
                f"{provider.title()} local monthly cap of {limit} successful requests is reached."
            )
        conn.execute(
            """
            INSERT INTO provider_usage (
              provider, period, attempted_requests, successful_requests, reserved_requests,
              tracked_since, updated_at
            ) VALUES (?, ?, 1, 0, 1, ?, ?)
            ON CONFLICT(provider, period) DO UPDATE SET
              attempted_requests=provider_usage.attempted_requests + 1,
              reserved_requests=provider_usage.reserved_requests + 1,
              updated_at=excluded.updated_at
            """,
            (provider, period, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def record_result(
    provider: str, status: int | None, *, successful: bool, settings: Settings | None = None
) -> None:
    settings = settings or get_settings()
    conn = connect(settings)
    try:
        conn.execute(
            """
            UPDATE provider_usage
            SET successful_requests=successful_requests + ?,
                reserved_requests=MAX(0, reserved_requests - 1),
                last_status=?, updated_at=?
            WHERE provider=? AND period=?
            """,
            (1 if successful else 0, status, utc_iso(), provider, _period()),
        )
        conn.commit()
    finally:
        conn.close()


def get_cached(
    provider: str, cache_key: str, ttl: timedelta, settings: Settings | None = None
) -> list[dict] | None:
    settings = settings or get_settings()
    conn = connect(settings)
    try:
        row = conn.execute(
            "SELECT payload_json, fetched_at FROM provider_cache WHERE provider=? AND cache_key=?",
            (provider, cache_key),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    try:
        fetched_at = datetime.fromisoformat(str(row["fetched_at"]))
        if datetime.now(UTC) - fetched_at > ttl:
            return None
        payload = json.loads(row["payload_json"])
        return payload if isinstance(payload, list) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def put_cached(
    provider: str, cache_key: str, payload: list[dict], settings: Settings | None = None
) -> None:
    settings = settings or get_settings()
    conn = connect(settings)
    try:
        conn.execute(
            """
            INSERT INTO provider_cache (provider, cache_key, payload_json, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(provider, cache_key) DO UPDATE SET
              payload_json=excluded.payload_json, fetched_at=excluded.fetched_at
            """,
            (provider, cache_key, json.dumps(payload, separators=(",", ":")), utc_iso()),
        )
        conn.commit()
    finally:
        conn.close()
