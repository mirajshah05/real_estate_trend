from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FreshnessStatus = Literal[
    "live",
    "fresh",
    "aging",
    "stale",
    "by_design_monthly",
    "unavailable",
]


class SourceFreshness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    provider: str
    dataset: str = ""
    observation_as_of: str | None = None
    http_last_modified: str | None = None
    stale: bool = True
    freshness_hours: float | None = None
    cadence: str = "unknown"
    note: str = ""
    status: FreshnessStatus = "unavailable"
    fetched_at: str | None = None


class FreshnessBlock(BaseModel):
    """Every API payload includes this block.

    Two clocks: ``http_last_modified`` (file) and ``observation_as_of`` (inside
    the file). ``stale`` follows the observation clock (7-day SLA).
    """

    model_config = ConfigDict(extra="forbid")

    computed_at: str
    overall: FreshnessStatus = "unavailable"
    source: str
    observation_as_of: str | None = None
    http_last_modified: str | None = None
    stale: bool = True
    freshness_hours: float | None = None
    cadence: str = "unknown"
    note: str = ""
    sources: list[SourceFreshness] = Field(default_factory=list)
