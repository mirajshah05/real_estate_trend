"""Market-level z-score outliers. Listing rules apply only when listings exist."""

from __future__ import annotations

import statistics

from realtykit.analysis.constants import (
    HIGH_DOM_MULT,
    HIGH_PRICE_MULT,
    LOW_PRICE_MULT,
    OUTLIER_Z_ABS,
)
from realtykit.models.analysis import OutlierRow


def _zscores(values: list[float]) -> list[float | None]:
    if len(values) < 3:
        return [None] * len(values)
    mean = statistics.fmean(values)
    sd = statistics.pstdev(values)
    if sd == 0:
        return [0.0] * len(values)
    return [(v - mean) / sd for v in values]


def metro_zscore_outliers(
    rows: list[dict],
    *,
    metric: str,
    z_abs: float = OUTLIER_Z_ABS,
    kind_label: str = "market outliers",
) -> list[OutlierRow]:
    """Flag metros with |z| ≥ 2 on a latest-period metric.

    ``rows`` items: geo_id, name, value. Label is market outliers, not homes.
    """
    usable = [r for r in rows if r.get("value") is not None]
    zs = _zscores([float(r["value"]) for r in usable])
    out: list[OutlierRow] = []
    for row, z in zip(usable, zs):
        if z is None or abs(z) < z_abs:
            continue
        out.append(
            OutlierRow(
                subject_id=row["geo_id"],
                name=row.get("name") or row["geo_id"],
                kind="geo",
                metric=metric,
                value=float(row["value"]),
                score=round(z, 4),
                reasons=[f"{kind_label}: {metric} z={z:.2f} vs metro cohort (|z|≥{z_abs})"],
            )
        )
    out.sort(key=lambda r: abs(r.score), reverse=True)
    return out


def listing_outliers(
    listings: list[dict],
    *,
    city_median_price: float | None,
    city_median_dom: float | None,
    high_price_mult: float = HIGH_PRICE_MULT,
    low_price_mult: float = LOW_PRICE_MULT,
    high_dom_mult: float = HIGH_DOM_MULT,
) -> list[OutlierRow]:
    """Listing is an outlier if price or DOM breaches documented multiples.

    Drop rows with missing price or missing geo. Unused until RentCast/MLS.
    """
    out: list[OutlierRow] = []
    for row in listings:
        price = row.get("price")
        geo_id = row.get("geo_id")
        if price is None or not geo_id:
            continue
        reasons: list[str] = []
        score = 0.0
        if city_median_price:
            if price >= city_median_price * high_price_mult:
                reasons.append(f"price ≥ city median × {high_price_mult}")
                score = max(score, price / city_median_price)
            elif price <= city_median_price * low_price_mult:
                reasons.append(f"price ≤ city median × {low_price_mult}")
                score = max(score, city_median_price / max(price, 1.0))
        dom = row.get("dom")
        if (
            dom is not None
            and city_median_dom
            and city_median_dom > 0
            and dom >= city_median_dom * high_dom_mult
        ):
            reasons.append(f"DOM ≥ city median × {high_dom_mult}")
            score = max(score, dom / city_median_dom)
        if not reasons:
            continue
        out.append(
            OutlierRow(
                subject_id=row["listing_id"],
                name=row.get("name") or row["listing_id"],
                kind="listing",
                metric="listing",
                value=float(price),
                score=round(score, 4),
                reasons=reasons,
                as_of=row.get("as_of") or row.get("listed_at") or row.get("observation_as_of"),
                source=row.get("source") or row.get("provider"),
            )
        )
    return out
