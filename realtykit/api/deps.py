from __future__ import annotations

from fastapi import HTTPException, Query, Request

from realtykit.settings import get_settings
from realtykit.store.db import connect, init_db
from realtykit.store.facts import resolve_geo
from realtykit.store.seed import seed_if_empty


def ensure_store() -> None:
    init_db()
    seed_if_empty()


def ensure_local_request(request: Request) -> None:
    client_host = ((request.client.host if request.client else "") or "").lower()
    raw_host = request.headers.get("host", "").lower()
    host_header = (
        raw_host[1:].split("]", 1)[0] if raw_host.startswith("[") else raw_host.split(":", 1)[0]
    )
    loopback = {"127.0.0.1", "::1", "localhost"}
    if client_host not in loopback or host_header not in loopback:
        raise HTTPException(
            status_code=403,
            detail={"code": "loopback_only", "message": "Provider-backed requests are local-only."},
        )
    # CORS alone does not block simple browser POSTs from an unrelated website.
    origin = request.headers.get("origin")
    allowed_origins = {*get_settings().cors_origin_list, f"{request.url.scheme}://{raw_host}"}
    if (origin is not None and origin not in allowed_origins) or (
        origin is None and request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise HTTPException(
            status_code=403,
            detail={"code": "untrusted_origin", "message": "Request origin is not allowed."},
        )


def geo_param(
    geo_id: str | None = Query(default=None),
    geo: str | None = Query(default=None),
) -> str:
    return resolve_geo(geo_id or geo)


def db_conn():
    ensure_store()
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
