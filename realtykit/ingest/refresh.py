"""Orchestrate probe → fetch → load. FRED never blocks housing ingest."""

from __future__ import annotations

import uuid
from typing import Any

from realtykit.freshness import build_freshness
from realtykit.log import log, utc_iso
from realtykit.providers import california_gis, compass, census_gazetteer, fred, redfin_research, rentcast
from realtykit.providers import yahoo_chart, zillow_research
from realtykit.settings import Settings, get_settings
from realtykit.store.db import init_db
from realtykit.store.seed import write_run

PROVIDER_ORDER = ("zillow", "redfin", "yahoo", "census", "government", "fred", "compass", "rentcast")


def refresh(
    *,
    providers: list[str] | None = None,
    force: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    wanted = {p.strip().lower() for p in (providers or PROVIDER_ORDER) if p.strip()}
    run_id = uuid.uuid4().hex[:12]
    started = utc_iso()
    conn = init_db(settings=settings)
    outcomes: list[dict] = []
    ok = True

    def record(result) -> None:
        items = result if isinstance(result, list) else [result]
        for item in items:
            outcomes.append(
                {
                    "source_id": item.source_id,
                    "provider": item.provider,
                    "status": item.status,
                    "observation_as_of": item.observation_as_of,
                    "http_last_modified": item.http_last_modified,
                    "rows": item.rows_upserted,
                    "note": item.note,
                }
            )

    try:
        if "zillow" in wanted:
            record(zillow_research.ingest(conn, settings, force=force))
        if "redfin" in wanted:
            record(redfin_research.ingest(conn, settings, force=force))
        if "yahoo" in wanted:
            record(yahoo_chart.ingest(conn, settings, force=force))
        if "census" in wanted:
            record(census_gazetteer.ingest(conn, settings, force=force))
        if "government" in wanted:
            record(california_gis.ingest(conn, settings, force=force))
        if "compass" in wanted:
            record(compass.ingest(conn))
        if "rentcast" in wanted:
            record(rentcast.ingest(conn, settings))
        if "fred" in wanted:
            # Last: never blocks housing even if this raises.
            try:
                record(fred.ingest(conn, settings, force=force))
            except Exception as exc:  # noqa: BLE001
                log("fred_nonblocking", error=str(exc))
                outcomes.append(
                    {
                        "source_id": "fred:MORTGAGE30US",
                        "provider": "fred",
                        "status": "error",
                        "note": f"non-blocking fail: {exc}",
                    }
                )
        conn.commit()
    except Exception:
        ok = False
        conn.rollback()
        raise
    finally:
        conn.close()

    finished = utc_iso()
    summary = {"run_id": run_id, "started_at": started, "finished_at": finished, "ok": ok, "outcomes": outcomes}
    write_run(run_id, started, finished, ok, summary)
    log("ingest_refresh", run_id=run_id, ok=ok, n=len(outcomes))
    freshness = build_freshness()
    return {**summary, "freshness": freshness.model_dump()}
