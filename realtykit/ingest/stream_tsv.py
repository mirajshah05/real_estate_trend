"""Gzip TSV stream with column projection and period filter."""

from __future__ import annotations

import csv
import gzip
from collections.abc import Iterator
from pathlib import Path


def iter_tsv_gz(
    path: Path,
    *,
    keep_columns: set[str] | None = None,
    period_duration: str | None = "30",
    property_type: str | None = "All Residential",
) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            if period_duration and row.get("PERIOD_DURATION") != period_duration:
                continue
            if property_type and row.get("PROPERTY_TYPE") != property_type:
                continue
            if keep_columns:
                yield {k: row.get(k) for k in keep_columns}
            else:
                yield row
