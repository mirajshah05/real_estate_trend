from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FetchOutcome:
    source_id: str
    provider: str
    dataset: str
    url: str
    status: str  # ok | skipped | unavailable | error
    fetched_at: str
    cadence: str = "unknown"
    observation_as_of: str | None = None
    http_last_modified: str | None = None
    etag: str | None = None
    content_sha256: str | None = None
    bytes: int | None = None
    freshness: str = "unavailable"
    note: str = ""
    path: Path | None = None
    rows_upserted: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def as_source_row(self) -> dict:
        return {
            "source_id": self.source_id,
            "provider": self.provider,
            "dataset": self.dataset,
            "url": self.url,
            "http_last_modified": self.http_last_modified,
            "etag": self.etag,
            "content_sha256": self.content_sha256,
            "bytes": self.bytes,
            "fetched_at": self.fetched_at,
            "observation_as_of": self.observation_as_of,
            "cadence": self.cadence,
            "freshness": self.freshness,
            "note": self.note,
        }
