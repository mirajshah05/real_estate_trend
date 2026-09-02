from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from realtykit.api.schemas import IngestRefreshBody, IngestRefreshResponse
from realtykit.freshness import build_freshness
from realtykit.ingest.refresh import refresh

router = APIRouter()


@router.post("/ingest/refresh", response_model=IngestRefreshResponse)
def ingest_refresh(request: Request, body: IngestRefreshBody | None = None) -> JSONResponse:
    host = (request.client.host if request.client else "") or ""
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(status_code=403, detail={"code": "loopback_only", "message": "Ingest is local-only."})
    payload = body or IngestRefreshBody()
    result = refresh(providers=payload.providers, force=payload.force)
    resp = IngestRefreshResponse(
        freshness=build_freshness(),
        run_id=result["run_id"],
        ok=bool(result.get("ok")),
        outcomes=result.get("outcomes") or [],
    )
    return JSONResponse(content=resp.model_dump(), headers={"Cache-Control": "no-store"})
