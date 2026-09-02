from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from realtykit.api.deps import ensure_local_request
from realtykit.api.schemas import IngestRefreshBody, IngestRefreshResponse
from realtykit.freshness import build_freshness
from realtykit.ingest.refresh import refresh

router = APIRouter()


@router.post("/ingest/refresh", response_model=IngestRefreshResponse)
def ingest_refresh(
    body: IngestRefreshBody | None = None,
    _local: None = Depends(ensure_local_request),
) -> JSONResponse:
    payload = body or IngestRefreshBody()
    result = refresh(providers=payload.providers, force=payload.force)
    resp = IngestRefreshResponse(
        freshness=build_freshness(),
        run_id=result["run_id"],
        ok=bool(result.get("ok")),
        outcomes=result.get("outcomes") or [],
    )
    return JSONResponse(content=resp.model_dump(), headers={"Cache-Control": "no-store"})
