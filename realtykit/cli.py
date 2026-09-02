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

    args = parser.parse_args(argv)
    if args.cmd == "serve":
        return _serve(args)
    if args.cmd == "ingest" and args.ingest_cmd == "refresh":
        return _refresh(args)
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


if __name__ == "__main__":
    raise SystemExit(main())
