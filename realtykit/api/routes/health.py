from fastapi import APIRouter, Depends

from realtykit import __version__
from realtykit.api.deps import ensure_store
from realtykit.api.schemas import HealthResponse
from realtykit.freshness import build_freshness

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(_ok: None = Depends(ensure_store)) -> HealthResponse:
    return HealthResponse(ok=True, service="realtykit", version=__version__, freshness=build_freshness())
