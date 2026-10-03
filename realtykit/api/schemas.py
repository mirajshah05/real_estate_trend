"""Request/response models. Explicit fields; unknown keys rejected."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from realtykit.models.analysis import CorrelationPair, OutlierRow
from realtykit.models.freshness import FreshnessBlock
from realtykit.models.listing import Listing, SaleEvent
from realtykit.models.market import KpiPoint

METRICS = frozenset(
    {
        "median_sale_price",
        "median_list_price",
        "zhvi",
        "price_change_yoy",
        "price_change_mom",
        "price_change_wow",
        "inventory",
        "new_listings",
        "days_on_market",
        "median_dom",
        "homes_sold",
        "pending",
        "inventory_wow",
        "inventory_yoy",
        "inventory_change",
        "gspc",
        "mortgage_30y",
    }
)
STOCK_SYMBOLS = frozenset({"^GSPC", "^IXIC", "^DJI", "GSPC", "IXIC", "DJI"})


class ForbidModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ForbidModel):
    ok: bool = True
    service: str = "realtykit"
    version: str = "0.1.0"
    freshness: FreshnessBlock


class FreshnessResponse(ForbidModel):
    freshness: FreshnessBlock
    goal: dict[str, Any]


class MapCity(ForbidModel):
    geo_id: str
    name: str
    state: str | None = None
    lat: float | None = None
    lon: float | None = None
    price: float | None = None
    inventory: float | None = None
    inventory_change: float | None = None
    mom: float | None = None
    yoy: float | None = None
    days_on_market: float | None = None
    value: float | None = None


class MapCitiesResponse(ForbidModel):
    freshness: FreshnessBlock
    metric: str
    period_end: str | None = None
    provider: str = "zillow"
    features: list[MapCity] = Field(default_factory=list)


class MapZipsResponse(ForbidModel):
    freshness: FreshnessBlock
    metric: str = "inventory"
    period_end: str | None = None
    provider: str = "zillow"
    features: list[MapCity] = Field(default_factory=list)
    note: str = ""


class ProviderUsage(ForbidModel):
    provider: str
    period: str
    attempted_requests: int = 0
    successful_requests: int = 0
    reserved_requests: int = 0
    limit: int | None = None
    warning_at: int | None = None
    remaining: int | None = None
    alert: str | None = None
    tracked_since: str | None = None
    last_status: int | None = None
    external_usage_unknown: bool = True


class MapListingsResponse(ForbidModel):
    freshness: FreshnessBlock
    listings: list[Listing] = Field(default_factory=list)
    usage: ProviderUsage | None = None
    cached: bool = False
    note: str = ""


class MapSalesResponse(ForbidModel):
    freshness: FreshnessBlock
    sales: list[SaleEvent] = Field(default_factory=list)
    usage: ProviderUsage | None = None
    cached: bool = False
    lookback_days: int = 365
    query_bounds: list[float] = Field(default_factory=list)
    record_limit: int = 200
    date_from: str | None = None
    date_to: str | None = None
    note: str = ""


class GovernmentArea(ForbidModel):
    area_id: str
    name: str
    state: str
    county: str
    parent_geo_id: str | None = None
    provider: str
    source_id: str
    lat: float
    lon: float
    parcel_count: int | None = None
    geometry: dict[str, Any]
    observation_as_of: str | None = None
    fetched_at: str
    note: str | None = None


class GovernmentAreasResponse(ForbidModel):
    freshness: FreshnessBlock
    features: list[GovernmentArea] = Field(default_factory=list)
    note: str = ""


class SearchResult(ForbidModel):
    geo_id: str
    name: str
    state: str | None = None
    lat: float | None = None
    lon: float | None = None
    kind: str = "geo"
    label: str | None = None
    market_geo_id: str | None = None


class SearchResponse(ForbidModel):
    freshness: FreshnessBlock
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    note: str = ""


class ResearchPoint(ForbidModel):
    t: str
    v: float


class ResearchMetric(ForbidModel):
    metric: str
    label: str
    value: float | None = None
    period_end: str | None = None
    cadence: str | None = None
    provider: str | None = None
    source_id: str | None = None
    status: str = "unavailable"


class ResearchSource(ForbidModel):
    source_id: str
    provider: str
    dataset: str = ""
    url: str = ""
    status: str = "unavailable"
    observation_as_of: str | None = None
    http_last_modified: str | None = None
    cadence: str = "unknown"
    note: str = ""


class ResearchResponse(ForbidModel):
    freshness: FreshnessBlock
    geo_id: str
    name: str | None = None
    state: str | None = None
    as_of: str | None = None
    metrics: list[ResearchMetric] = Field(default_factory=list)
    series: dict[str, list[ResearchPoint]] = Field(default_factory=dict)
    national_context: list[ResearchMetric] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)


class KpisResponse(ForbidModel):
    freshness: FreshnessBlock
    geo_id: str
    name: str | None = None
    as_of: str | None = None
    kpis: dict[str, KpiPoint]


class TrendPoint(ForbidModel):
    t: str
    v: float


class TrendsResponse(ForbidModel):
    freshness: FreshnessBlock
    geo_id: str
    cadence: str = "weekly"
    series: dict[str, list[TrendPoint]]


class CorrelationResponse(ForbidModel):
    freshness: FreshnessBlock
    geo_id: str
    aligned_cadence: str = "weekly"
    n: int
    status: str
    pairs: list[CorrelationPair]
    disclaimer: str


class OutliersResponse(ForbidModel):
    freshness: FreshnessBlock
    kind: str = "geo"
    method: str = "metro_zscore"
    label: str = "market outliers"
    rows: list[OutlierRow]


class StockLast(ForbidModel):
    t: str | None = None
    close: float | None = None
    pct_above_52w_low: float | None = None
    drawdown_52w: float | None = None
    dip: bool = False


class StocksDipsResponse(ForbidModel):
    freshness: FreshnessBlock
    symbol: str
    last: StockLast
    dips: list[dict[str, Any]] = Field(default_factory=list)
    lookback_days: int = 365
    threshold_window_weeks: int = 52
    event_window_start: str | None = None
    history_start: str | None = None
    history_end: str | None = None
    history_points: int = 0
    note: str = ""


class IngestRefreshBody(ForbidModel):
    providers: list[str] | None = None
    force: bool = False


class IngestRefreshResponse(ForbidModel):
    freshness: FreshnessBlock
    run_id: str
    ok: bool
    outcomes: list[dict[str, Any]] = Field(default_factory=list)


class RentalImportBody(ForbidModel):
    filename: str = Field(min_length=1, max_length=128)
    format: Literal["csv", "json"]
    content: str = Field(min_length=1, max_length=5 * 1024 * 1024)


class RentalImportResponse(ForbidModel):
    import_id: str
    inserted: int
    updated: int
    rejected: int = 0
    cities: list[str]
    date_min: str
    date_max: str


class RentalTrendSegment(ForbidModel):
    month: str
    bedrooms: int
    property_type: str
    listing_status: str
    availability_status: str = "unknown"
    count: int
    median_rent: float
    average_rent: float
    min_rent: float
    max_rent: float


class RentalMarketIndexPoint(ForbidModel):
    month: str
    value: float


class RentalMarketIndex(ForbidModel):
    provider: str
    source_id: str
    metric: str
    home_type: str
    city: str
    as_of: str
    points: list[RentalMarketIndexPoint] = Field(default_factory=list)


class RentalTrendsResponse(ForbidModel):
    city: str
    months: int
    date_from: str
    date_to: str
    observation_count: int
    first_observed_on: str | None = None
    last_observed_on: str | None = None
    segments: list[RentalTrendSegment] = Field(default_factory=list)
    market_indices: list[RentalMarketIndex] = Field(default_factory=list)
    rentcast_usage: ProviderUsage | None = None


class StoredRentalObservation(ForbidModel):
    observation_id: str
    import_id: str
    source: str
    observed_on: str
    city: str
    zip_code: str | None = None
    neighborhood: str | None = None
    monthly_rent: float
    bedrooms: int
    bathrooms: float | None = None
    property_type: str
    listing_status: str
    availability_status: str = "unknown"
    sqft: float | None = None
    year_built: int | None = None
    amenities: list[str] = Field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    removed_on: str | None = None
    last_seen_on: str | None = None
    imported_at: str


class RentalObservationsResponse(ForbidModel):
    total: int
    limit: int
    offset: int
    observations: list[StoredRentalObservation] = Field(default_factory=list)


class ApiError(ForbidModel):
    error: dict[str, str]
