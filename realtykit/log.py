"""Structured JSON logs. Never log secrets or raw tokens."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

_REDACT_KEYS = frozenset(
    {"api_key", "key", "token", "secret", "password", "authorization", "fred_api_key", "rentcast_api_key"}
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact(value: object) -> object:
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in _REDACT_KEYS else _redact(v)) for k, v in value.items()}
    return value


def log(event: str, **fields: object) -> None:
    rec = {"ts": utc_iso(), "event": event, **_redact(fields)}
    sys.stderr.write(json.dumps(rec, default=str) + "\n")
