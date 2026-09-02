from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CorrelationPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: str
    b: str
    lag_weeks: int = 0
    pearson: float | None = None
    n: int = 0
    note: str = ""


class CorrelationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aligned_cadence: str = "weekly"
    n: int = 0
    status: str = "ok"
    pairs: list[CorrelationPair] = Field(default_factory=list)
    disclaimer: str = (
        "Correlation is not causation. Aligned weekly observations do not imply "
        "that housing, equities, or mortgage rates cause each other."
    )


class OutlierRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    name: str
    kind: str = "geo"
    metric: str
    value: float | None = None
    score: float
    reasons: list[str] = Field(default_factory=list)
    as_of: str | None = None
    source: str | None = None
