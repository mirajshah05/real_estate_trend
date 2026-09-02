from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MarketFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geo_id: str
    period_end: str
    metric: str
    value: float
    provider: str
    cadence: str = "weekly"


class KpiPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float | None = None
    delta_wow: float | None = None
    delta_mom: float | None = None
    delta_yoy: float | None = None
    delta_1d: float | None = None
    drawdown_52w: float | None = None
    status: str = "stale"
