#!/usr/bin/env python3
"""Local smoke: GET /api/freshness and /api/kpis?geo_id=… on loopback :8770.

Exit 1 on connection failure or a payload that has no as_of /
observation_as_of. Does not invent keys — only inspects fields the API
already returned.

  python scripts/probes/freshness_probe.py
  python scripts/probes/freshness_probe.py --geo-id "Austin, TX"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_BASE = "http://127.0.0.1:8770"
DEFAULT_GEO = "United States"
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
GEO_RE = re.compile(r"^[A-Za-z0-9 ,._:-]{1,80}$")
TIMEOUT_S = 8.0
AS_OF_KEYS = ("as_of", "observation_as_of")


def _loopback_base() -> str:
    raw = os.environ.get("REALTYKIT_API", DEFAULT_BASE).strip() or DEFAULT_BASE
    parsed = urllib.parse.urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        print(
            f"refusing non-loopback REALTYKIT_API host {host!r}; "
            f"use {DEFAULT_BASE}",
            file=sys.stderr,
        )
        sys.exit(1)
    scheme = parsed.scheme or "http"
    if scheme not in {"http", "https"}:
        print(f"unsupported scheme {scheme!r}", file=sys.stderr)
        sys.exit(1)
    port = parsed.port or (8770 if parsed.hostname else None)
    netloc = parsed.hostname or "127.0.0.1"
    if port:
        netloc = f"{netloc}:{port}"
    return f"{scheme}://{netloc}"


def _get(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "RealtyKitFreshnessProbe/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            raw = resp.read()
            if resp.status != 200:
                print(f"{url} -> HTTP {resp.status}", file=sys.stderr)
                sys.exit(1)
    except urllib.error.HTTPError as exc:
        print(f"{url} -> HTTP {exc.code}", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"connection failed: {url} ({exc})", file=sys.stderr)
        sys.exit(1)
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"invalid JSON from {url}: {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(body, dict):
        print(f"{url} did not return a JSON object", file=sys.stderr)
        sys.exit(1)
    return body


def _as_of_paths(node: Any, prefix: str = "") -> list[str]:
    """Return JSON paths where as_of / observation_as_of already exist."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, val in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in AS_OF_KEYS and val not in (None, ""):
                found.append(path)
            found.extend(_as_of_paths(val, path))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found.extend(_as_of_paths(item, f"{prefix}[{i}]"))
    return found


def _require_as_of(label: str, payload: dict[str, Any]) -> list[str]:
    paths = _as_of_paths(payload)
    if not paths:
        print(
            f"{label}: missing as_of / observation_as_of on the returned payload",
            file=sys.stderr,
        )
        sys.exit(1)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--geo-id",
        default=DEFAULT_GEO,
        help="geo_id query for /api/kpis (default: United States)",
    )
    args = parser.parse_args(argv)
    if not GEO_RE.fullmatch(args.geo_id):
        print("invalid geo_id", file=sys.stderr)
        return 1

    base = _loopback_base()
    freshness_url = urllib.parse.urljoin(base, "/api/freshness")
    kpis_url = (
        urllib.parse.urljoin(base, "/api/kpis")
        + "?"
        + urllib.parse.urlencode({"geo_id": args.geo_id})
    )

    freshness = _get(freshness_url)
    freshness_paths = _require_as_of("GET /api/freshness", freshness)

    kpis = _get(kpis_url)
    kpis_paths = _require_as_of(f"GET /api/kpis?geo_id={args.geo_id}", kpis)

    report = {
        "ok": True,
        "base": base,
        "freshness_as_of_paths": freshness_paths,
        "kpis_as_of_paths": kpis_paths,
        "kpis_geo_id": args.geo_id,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
