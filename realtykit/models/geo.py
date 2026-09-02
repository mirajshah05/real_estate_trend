from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

GeoLevel = Literal["nation", "state", "metro", "city", "zip"]


class GeoId(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geo_id: str
    name: str
    level: GeoLevel = "metro"
    state: str | None = None
    lat: float | None = None
    lon: float | None = None
