"""CLI is ingest/serve only. The dashboard is the product."""

from __future__ import annotations

import argparse
import json
import sys

from realtykit import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="realtykit", description="RealtyKit ingest + API")
    parser.add_argument("--version", action="version", version=f"realtykit {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Start the local FastAPI server")
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--host", default=None)

    ingest = sub.add_parser("ingest", help="Provider pull")
    ingest_sub = ingest.add_subparsers(dest="ingest_cmd", required=True)
    refresh_p = ingest_sub.add_parser("refresh", help="Fetch research dumps into SQLite")
    refresh_p.add_argument("--force", action="store_true", help="Ignore ETag / Last-Modified")
    refresh_p.add_argument(
        "--providers",
        default="",
        help="Comma list: zillow,redfin,yahoo,census,government,fred,compass,rentcast",
    )
    rentals_p = ingest_sub.add_parser(
        "rentals", help="Collect target-city rental observations and official ZORI indices"
    )
    rentals_p.add_argument("--providers", default="zillow,rentcast", help="zillow,rentcast")
    rentals_p.add_argument(
        "--cities",
        default="San Jose,Sunnyvale,Mountain View,Palo Alto",
        help="Comma-separated target cities",
    )
    rentals_p.add_argument("--statuses", default="active,inactive", help="active,inactive")
    rentals_p.add_argument("--limit-per-query", type=int, default=100)
    rentals_p.add_argument("--days-old", type=int, default=1095)
    rentals_p.add_argument("--force", action="store_true", help="Ignore provider caches")

    args = parser.parse_args(argv)
    if args.cmd == "serve":
        return _serve(args)
    if args.cmd == "ingest" and args.ingest_cmd == "refresh":
        return _refresh(args)
    if args.cmd == "ingest" and args.ingest_cmd == "rentals":
        return _rentals(args)
    parser.error("unknown command")
    return 2


def _serve(args: argparse.Namespace) -> int:
    from realtykit.settings import get_settings

    settings = get_settings()
    host = args.host or settings.host
    port = args.port or settings.port
    if host not in {"127.0.0.1", "localhost"}:
        print("Refusing non-loopback bind. Use --host 127.0.0.1", file=sys.stderr)
        return 2
    import uvicorn

    uvicorn.run("realtykit.api.main:app", host=host, port=port, reload=False)
    return 0


def _refresh(args: argparse.Namespace) -> int:
    from realtykit.ingest.refresh import refresh

    providers = [p.strip() for p in args.providers.split(",") if p.strip()] or None
    result = refresh(providers=providers, force=args.force)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


def _rentals(args: argparse.Namespace) -> int:
    import httpx

    from realtykit.ingest.rental_collection import collect_rentcast
    from realtykit.providers import zillow_research
    from realtykit.settings import get_settings
    from realtykit.store.db import init_db

    providers = {value.strip().lower() for value in args.providers.split(",") if value.strip()}
    if not providers or providers - {"zillow", "rentcast"}:
        print("--providers must contain only zillow and/or rentcast", file=sys.stderr)
        return 2
    cities = tuple(value.strip() for value in args.cities.split(",") if value.strip())
    statuses = tuple(value.strip().lower() for value in args.statuses.split(",") if value.strip())
    settings = get_settings()
    conn = init_db(settings=settings)
    result: dict = {"ok": True, "providers": {}}
    try:
        if "zillow" in providers:
            outcomes = zillow_research.ingest_zori(conn, settings, force=args.force)
            conn.commit()
            result["providers"]["zillow"] = [
                {
                    "source_id": outcome.source_id,
                    "status": outcome.status,
                    "rows": outcome.rows_upserted,
                    "observation_as_of": outcome.observation_as_of,
                    "note": outcome.note,
                }
                for outcome in outcomes
            ]
            result["ok"] = result["ok"] and all(outcome.status == "ok" for outcome in outcomes)
        if "rentcast" in providers:
            result["providers"]["rentcast"] = collect_rentcast(
                conn,
                settings=settings,
                cities=cities,
                statuses=statuses,
                limit_per_query=args.limit_per_query,
                days_old=args.days_old,
                force=args.force,
            )
    except httpx.HTTPStatusError as exc:
        result["ok"] = False
        result["error"] = {
            "provider": "rentcast",
            "status": exc.response.status_code,
            "message": "RentCast rejected the bounded collection request.",
        }
    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        conn.close()
    if "rentcast" in providers:
        from realtykit.store.provider_usage import usage_snapshot

        result["rentcast_usage"] = usage_snapshot("rentcast", settings)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
