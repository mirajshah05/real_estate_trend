"""Structured JSON logs. Never log secrets or raw tokens."""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime

_REDACT_KEYS = frozenset(
    {
        "api_key",
        "key",
        "token",
        "secret",
        "password",
        "authorization",
        "fred_api_key",
        "rentcast_api_key",
        "attom_api_key",
    }
)
_QUERY_SECRET = re.compile(r"(?i)([?&](?:api_?key|apikey|key|token|secret|password)=)[^&\s]+")
_BEARER_SECRET = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact(value: object) -> object:
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in _REDACT_KEYS else _redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _BEARER_SECRET.sub(r"\1***", _QUERY_SECRET.sub(r"\1***", value))
    return value


def log(event: str, **fields: object) -> None:
    rec = {"ts": utc_iso(), "event": event, **_redact(fields)}
    sys.stderr.write(json.dumps(rec, default=str) + "\n")
