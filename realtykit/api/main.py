"""FastAPI app. Bind 127.0.0.1. CORS for Vite."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from realtykit.api.routes import (
    correlation,
    freshness,
    government,
    health,
    ingest,
    kpis,
    map,
    outliers,
    rental_estimate,
    rentals,
    research,
    search,
    stocks,
    trends,
)
from realtykit.settings import get_settings
from realtykit.store.db import init_db
from realtykit.store.seed import seed_if_empty

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_if_empty()
    yield


app = FastAPI(title="RealtyKit", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(freshness.router, prefix="/api")
app.include_router(map.router, prefix="/api")
app.include_router(government.router, prefix="/api")
app.include_router(kpis.router, prefix="/api")
app.include_router(trends.router, prefix="/api")
app.include_router(correlation.router, prefix="/api")
app.include_router(outliers.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(rentals.router, prefix="/api")
app.include_router(rental_estimate.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(research.router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not include submitted values, which may contain private imported data.
    errors = exc.errors()
    unknown_metric = any("metric" in error.get("loc", ()) for error in errors)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "unknown_metric" if unknown_metric else "invalid_request",
                "message": "Unsupported metric." if unknown_metric else "Invalid request.",
            }
        },
    )


@app.exception_handler(HTTPException)
async def _http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        error = {"code": str(detail["code"]), "message": str(detail["message"])}
    else:
        error = {"code": "http_error", "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": error}, headers=exc.headers)
