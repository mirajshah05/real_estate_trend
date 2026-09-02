from __future__ import annotations

from fastapi import Query

from realtykit.store.db import connect, init_db
from realtykit.store.facts import resolve_geo
from realtykit.store.seed import seed_if_empty


def ensure_store() -> None:
    init_db()
    seed_if_empty()


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
