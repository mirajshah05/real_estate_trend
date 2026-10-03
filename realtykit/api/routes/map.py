from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from realtykit.analysis.outliers import listing_outliers
from realtykit.api.deps import ensure_local_request, ensure_store
from realtykit.api.schemas import (
    METRICS,
    MapCitiesResponse,
    MapCity,
    MapListingsResponse,
    MapSalesResponse,
    MapZipsResponse,
)
from realtykit.freshness import build_freshness
from realtykit.models.listing import Listing, SaleEvent
from realtykit.providers import rentcast
from realtykit.settings import get_settings
from realtykit.store.db import connect
from realtykit.store.facts import latest_facts
from realtykit.store.listings import upsert_listings
from realtykit.store.provider_usage import ProviderQuotaExceeded, usage_snapshot
from realtykit.store.sales import upsert_sales

router = APIRouter()

_CITY_METRICS = {
    "zhvi": "zhvi",
    "price_change_mom": "price_change_mom",
    "price_change_yoy": "price_change_yoy",
    "price_change_wow": "price_change_wow",
    "inventory": "inventory",
    "inventory_change": "inventory_wow",
    "inventory_wow": "inventory_wow",
    "inventory_yoy": "inventory_yoy",
    "new_listings": "new_listings",
    "days_on_market": "days_on_market",
}


def _period(value: str) -> str | None:
    if value == "latest":
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_period", "message": "period must be latest or YYYY-MM-DD."},
        ) from None
    return value


def _listing_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        west, south, east, north = (float(part.strip()) for part in value.split(","))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_bbox", "message": "bbox must be west,south,east,north."},
        ) from None
    if not (
        -180 <= west < east <= 180
        and -90 <= south < north <= 90
        and east - west <= 2.5
        and north - south <= 2.5
    ):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_bbox",
                "message": "Listing bbox must be valid and no larger than 2.5 degrees.",
            },
        )
    return west, south, east, north


def _nearest_metro(lat: float, lon: float, conn) -> str | None:
    row = conn.execute(
        """
        SELECT geo_id FROM geos
        WHERE level = 'metro' AND lat IS NOT NULL AND lon IS NOT NULL
        ORDER BY (lat - ?) * (lat - ?) + (lon - ?) * (lon - ?)
        LIMIT 1
        """,
        (lat, lat, lon, lon),
    ).fetchone()
    return row["geo_id"] if row else None


@router.get("/map/cities", response_model=MapCitiesResponse)
def map_cities(
    metric: str = Query(default="price_change_yoy"),
    period: str = Query(default="latest"),
    provider: str = Query(default="auto"),
    limit: int = Query(default=1200, ge=1, le=4000),
    _ok: None = Depends(ensure_store),
) -> MapCitiesResponse:
    if metric not in _CITY_METRICS:
        raise HTTPException(
            status_code=422,
            detail={"code": "unknown_metric", "message": f"Unknown map metric: {metric}"},
        )
    if provider not in {"auto", "zillow"}:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "provider_unavailable",
                "message": "The city map currently has Zillow Research metro facts only.",
            },
        )
    requested_period = _period(period)
    selected_metric = _CITY_METRICS[metric]
    conn = connect()
    try:

        def latest(metric_name: str) -> str | None:
            row = conn.execute(
                "SELECT MAX(period_end) AS p FROM market_facts WHERE metric = ? AND provider = 'zillow'",
                (metric_name,),
            ).fetchone()
            return row["p"] if row else None

        def target_period(metric_name: str) -> str | None:
            return requested_period or latest(metric_name)

        selected_period = target_period(selected_metric)
        zhvi_p = target_period("zhvi")
        inv_p = target_period("inventory")
        mom_p = target_period("price_change_mom")
        yoy_p = target_period("price_change_yoy")
        dom_p = target_period("days_on_market")
        inv_change_p = target_period("inventory_wow")
        sql = """
            SELECT g.geo_id, g.name, g.state, g.lat, g.lon,
                   (SELECT value FROM market_facts
                     WHERE geo_id = g.geo_id AND metric = ? AND provider = 'zillow'
                       AND period_end = ?) AS selected_value,
                   (SELECT value FROM market_facts
                     WHERE geo_id = g.geo_id AND metric = 'zhvi' AND provider = 'zillow'
                       AND period_end = ? LIMIT 1) AS price,
                   (SELECT value FROM market_facts
                     WHERE geo_id = g.geo_id AND metric = 'inventory' AND provider = 'zillow'
                       AND period_end = ? LIMIT 1) AS inventory,
                   (SELECT value FROM market_facts
                     WHERE geo_id = g.geo_id AND metric = 'price_change_mom' AND provider = 'zillow'
                       AND period_end = ? LIMIT 1) AS mom,
                   (SELECT value FROM market_facts
                     WHERE geo_id = g.geo_id AND metric = 'price_change_yoy' AND provider = 'zillow'
                       AND period_end = ? LIMIT 1) AS yoy,
                   (SELECT value FROM market_facts
                     WHERE geo_id = g.geo_id AND metric = 'days_on_market' AND provider = 'zillow'
                       AND period_end = ? LIMIT 1) AS days_on_market,
                   (SELECT value FROM market_facts
                     WHERE geo_id = g.geo_id AND metric = 'inventory_wow' AND provider = 'zillow'
                       AND period_end = ? LIMIT 1) AS inventory_change
            FROM geos g
            WHERE g.level IN ('metro', 'nation')
              AND (g.geo_id = 'nation:US' OR (g.lat IS NOT NULL AND g.lon IS NOT NULL))
            ORDER BY CASE WHEN selected_value IS NULL THEN 1 ELSE 0 END, g.name
            LIMIT ?
        """
        rows = [
            dict(r)
            for r in conn.execute(
                sql,
                (
                    selected_metric,
                    selected_period,
                    zhvi_p,
                    inv_p,
                    mom_p,
                    yoy_p,
                    dom_p,
                    inv_change_p,
                    limit,
                ),
            ).fetchall()
            if r["price"] is not None or r["inventory"] is not None
        ]
    finally:
        conn.close()

    features: list[MapCity] = []
    for r in rows:
        if (r.get("lat") is None or r.get("lon") is None) and r.get("geo_id") != "nation:US":
            continue
        price = r.get("price")
        features.append(
            MapCity(
                geo_id=r["geo_id"],
                name=r["name"],
                state=r.get("state"),
                lat=r.get("lat"),
                lon=r.get("lon"),
                price=round(price) if price is not None else None,
                inventory=r.get("inventory"),
                inventory_change=r.get("inventory_change"),
                mom=r.get("mom"),
                yoy=r.get("yoy"),
                days_on_market=r.get("days_on_market"),
                value=r.get("selected_value"),
            )
        )
    return MapCitiesResponse(
        freshness=build_freshness(prefer_source="zillow:zhvi_metro"),
        metric=metric,
        period_end=selected_period,
        provider="zillow",
        features=features,
    )


@router.get("/map/zips", response_model=MapZipsResponse)
def map_zips(
    metro: str | None = Query(default=None),
    bbox: str | None = Query(default=None),
    metric: str = Query(default="inventory"),
    period: str = Query(default="latest"),
    limit: int = Query(default=1500, ge=1, le=5000),
    _ok: None = Depends(ensure_store),
) -> MapZipsResponse:
    if metric not in METRICS:
        metric = "inventory"
    conn = connect()
    try:
        if bbox:
            try:
                west, south, east, north = (float(p.strip()) for p in bbox.split(","))
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400, detail="bbox must be west,south,east,north"
                ) from None
            if east < west or north < south or (east - west) > 3 or (north - south) > 3:
                raise HTTPException(
                    status_code=400, detail="bbox must be a valid area no larger than 3 degrees"
                )
        elif metro:
            anchor = conn.execute(
                "SELECT lat, lon FROM geos WHERE geo_id = ? OR lower(name) = lower(?) LIMIT 1",
                (metro, metro),
            ).fetchone()
            if not anchor or anchor["lat"] is None or anchor["lon"] is None:
                return MapZipsResponse(
                    freshness=build_freshness(prefer_source="zillow:inv_week_zip"),
                    metric=metric,
                    note="Tracked ZIP inventory is not available for this metro.",
                )
            lat, lon = float(anchor["lat"]), float(anchor["lon"])
            west, east, south, north = lon - 1.5, lon + 1.5, lat - 1.5, lat + 1.5
        else:
            return MapZipsResponse(
                freshness=build_freshness(prefer_source="zillow:inv_week_zip"),
                metric=metric,
                note="ZIP map requires a metro or a viewport bbox.",
            )

        period_end = period if period != "latest" else None
        if period_end is None:
            row = conn.execute(
                "SELECT MAX(period_end) AS period_end FROM market_facts "
                "WHERE metric = ? AND provider = 'zillow' AND source_id = 'zillow:inv_week_zip'",
                (metric,),
            ).fetchone()
            period_end = row["period_end"] if row else None
        if not period_end:
            return MapZipsResponse(
                freshness=build_freshness(prefer_source="census:zcta_2024"),
                metric=metric,
                note="ZIP inventory is not ingested yet. Run `realtykit ingest refresh --providers zillow,census`.",
            )

        rows = conn.execute(
            """
            SELECT g.geo_id, g.name, g.state,
                   COALESCE(g.lat, c.lat) AS lat,
                   COALESCE(g.lon, c.lon) AS lon,
                   f.value
            FROM market_facts f
            JOIN geos g ON g.geo_id = f.geo_id
            LEFT JOIN geos c ON c.geo_id = 'census:zcta:' || g.name
            WHERE f.metric = ? AND f.provider = 'zillow' AND f.source_id = 'zillow:inv_week_zip'
              AND f.period_end = ?
              AND COALESCE(g.lat, c.lat) BETWEEN ? AND ?
              AND COALESCE(g.lon, c.lon) BETWEEN ? AND ?
            ORDER BY f.value DESC
            LIMIT ?
            """,
            (metric, period_end, south, north, west, east, limit),
        ).fetchall()
    finally:
        conn.close()

    features = [
        MapCity(
            geo_id=row["geo_id"],
            name=row["name"],
            state=row["state"],
            lat=row["lat"],
            lon=row["lon"],
            inventory=row["value"],
            value=row["value"],
        )
        for row in rows
        if row["lat"] is not None and row["lon"] is not None
    ]
    return MapZipsResponse(
        freshness=build_freshness(prefer_source="zillow:inv_week_zip"),
        metric=metric,
        period_end=period_end,
        features=features,
        note="ZIP inventory is a weekly Zillow Research observation; centroids come from Census ZCTA geography.",
    )


@router.get("/map/listings", response_model=MapListingsResponse)
def map_listings(
    bbox: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    status: str = Query(default="active"),
    _ok: None = Depends(ensure_store),
    _local: None = Depends(ensure_local_request),
) -> MapListingsResponse:
    settings = get_settings()
    if not bbox:
        raise HTTPException(
            status_code=400,
            detail={"code": "bbox_required", "message": "Listing map requires a viewport bbox."},
        )
    west, south, east, north = _listing_bbox(bbox)
    if not settings.has_rentcast_key:
        raise HTTPException(
            503,
            detail={
                "code": "provider_key_missing",
                "message": "RentCast is not configured in the running backend. Add RENTCAST_API_KEY and restart the backend.",
            },
        )
    listings: list[Listing] = []
    cached = False
    if settings.has_rentcast_key:
        try:
            raw, cached = rentcast.fetch_bbox(
                west=west,
                south=south,
                east=east,
                north=north,
                limit=limit,
                settings=settings,
            )
            # Store the viewport slice so /api/outliers?kind=listing can report
            # the same homes the map just rendered.
            if raw:
                upsert_conn = connect()
                try:
                    for row in raw:
                        row["geo_id"] = _nearest_metro(row["lat"], row["lon"], upsert_conn)
                    for geo_id in {row.get("geo_id") for row in raw if row.get("geo_id")}:
                        median_price_rows = latest_facts("zhvi", geo_id=geo_id, conn=upsert_conn)
                        median_dom_rows = latest_facts(
                            "days_on_market", geo_id=geo_id, conn=upsert_conn
                        )
                        found = listing_outliers(
                            [row for row in raw if row.get("geo_id") == geo_id],
                            city_median_price=median_price_rows[0]["value"]
                            if median_price_rows
                            else None,
                            city_median_dom=median_dom_rows[0]["value"]
                            if median_dom_rows
                            else None,
                        )
                        by_id = {item.subject_id: item for item in found}
                        for row in raw:
                            flag = by_id.get(row["listing_id"])
                            if flag:
                                row["outlier_score"] = flag.score
                                row["outlier_reasons"] = flag.reasons
                    upsert_listings(raw, upsert_conn)
                    upsert_conn.commit()
                finally:
                    upsert_conn.close()
            listings = [
                Listing.model_validate(row)
                for row in raw
                if (row.get("status") or "active") == status or status == "all"
            ]
        except ProviderQuotaExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail={"code": "provider_quota_reached", "message": str(exc)},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            message = (
                "RentCast denied this request. Check the API key and plan access in the RentCast dashboard."
                if status in {401, 403}
                else f"RentCast returned HTTP {status}."
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "provider_auth_denied"
                    if status in {401, 403}
                    else "provider_unavailable",
                    "message": message,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail={"code": "listing_payload_invalid", "message": "Invalid listing payload."},
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "provider_unavailable",
                    "message": "RentCast request failed. Check provider availability.",
                },
            ) from exc
    return MapListingsResponse(
        freshness=build_freshness(prefer_source="rentcast:listings"),
        listings=listings,
        usage=usage_snapshot("rentcast", settings) if settings.has_rentcast_key else None,
        cached=cached if settings.has_rentcast_key else False,
        note=(
            "Address-level active listings in the visible viewport. This is separate from Zillow's "
            "weekly metro new-listings aggregate. Cached for six hours to protect the API allowance."
        ),
    )


@router.get("/map/sales", response_model=MapSalesResponse)
def map_sales(
    bbox: str | None = Query(default=None),
    lookback_days: int = Query(default=365, ge=1, le=3650),
    limit: int = Query(default=200, ge=1, le=500),
    _ok: None = Depends(ensure_store),
    _local: None = Depends(ensure_local_request),
) -> MapSalesResponse:
    settings = get_settings()
    if not bbox:
        raise HTTPException(
            status_code=400,
            detail={"code": "bbox_required", "message": "Sale map requires a viewport bbox."},
        )
    west, south, east, north = _listing_bbox(bbox)
    if not settings.has_rentcast_key:
        raise HTTPException(
            503,
            detail={
                "code": "provider_key_missing",
                "message": "RentCast is not configured in the running backend. Add RENTCAST_API_KEY and restart the backend.",
            },
        )
    sales: list[SaleEvent] = []
    cached = False
    if settings.has_rentcast_key:
        try:
            raw, cached = rentcast.fetch_sold_bbox(
                west=west,
                south=south,
                east=east,
                north=north,
                lookback_days=lookback_days,
                limit=limit,
                settings=settings,
            )
            if raw:
                conn = connect()
                try:
                    upsert_sales(raw, conn)
                    conn.commit()
                finally:
                    conn.close()
            sales = [SaleEvent.model_validate(row) for row in raw]
        except ProviderQuotaExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail={"code": "provider_quota_reached", "message": str(exc)},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            message = (
                "RentCast denied this request. Check the API key and plan access in the RentCast dashboard."
                if status in {401, 403}
                else f"RentCast returned HTTP {status}."
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "provider_auth_denied"
                    if status in {401, 403}
                    else "provider_unavailable",
                    "message": message,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail={"code": "sale_payload_invalid", "message": "Invalid sale payload."},
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "provider_unavailable",
                    "message": "RentCast request failed. Check provider availability.",
                },
            ) from exc
    return MapSalesResponse(
        freshness=build_freshness(prefer_source="rentcast:listings"),
        sales=sales,
        usage=usage_snapshot("rentcast", settings) if settings.has_rentcast_key else None,
        cached=cached,
        lookback_days=lookback_days,
        query_bounds=[west, south, east, north],
        record_limit=limit,
        date_from=(datetime.now(UTC).date() - timedelta(days=lookback_days)).isoformat(),
        date_to=datetime.now(UTC).date().isoformat(),
        note=(
            "RentCast property-record sale events for the visible viewport. Owner and assessment "
            "fields are discarded. County recording delays can be several weeks or months."
        ),
    )
