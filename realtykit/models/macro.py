from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MacroPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    ts: str
    value: float
    provider: str


class DipEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t: str
    close: float
    kind: str
    from_peak: float | None = None
    peak_t: str | None = None
    pct_above_52w_low: float | None = None
