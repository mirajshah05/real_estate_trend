"""Deterministic, explainable rent estimates from historical comparables.

This module intentionally implements a bounded comparable analysis rather than
claiming statistical or ML precision.  Every adjustment is exposed to callers,
and sparse evidence produces a wider range and lower confidence.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from datetime import UTC, date, datetime
from statistics import median
from typing import Any

PROPERTY_TYPE_FACTORS = {
    "apartment": 1.00,
    "townhouse": 1.10,
    "single_family": 1.20,
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _amenities(value: Any) -> set[str]:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            decoded = value.split(",")
        value = decoded
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {item for raw in value if (item := _text(raw))}


def _round_rent(value: float) -> float:
    return float(round(value / 10.0) * 10)


def _bounded_ratio(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _feature_score(target: dict[str, Any], comp: dict[str, Any], as_of: date) -> float:
    """Similarity in [0, 1], with location and core unit type weighted highest."""

    city = 1.0 if _text(target.get("city")) == _text(comp.get("city")) else 0.15

    target_neighborhood = _text(target.get("neighborhood"))
    comp_neighborhood = _text(comp.get("neighborhood"))
    neighborhood = (
        1.0
        if target_neighborhood and target_neighborhood == comp_neighborhood
        else 0.0
        if target_neighborhood and comp_neighborhood
        else 0.4
    )

    target_zip = _text(target.get("zip_code"))
    comp_zip = _text(comp.get("zip_code"))
    zip_score = (
        1.0
        if target_zip and target_zip == comp_zip
        else 0.0
        if target_zip and comp_zip
        else 0.4
    )

    target_beds = _number(target.get("bedrooms")) or 0.0
    comp_beds = _number(comp.get("bedrooms")) or 0.0
    bed_score = max(0.0, 1.0 - abs(target_beds - comp_beds) / 2.0)

    target_baths = _number(target.get("bathrooms"))
    comp_baths = _number(comp.get("bathrooms"))
    bath_score = (
        max(0.0, 1.0 - abs(target_baths - comp_baths) / 2.0)
        if target_baths is not None and comp_baths is not None
        else 0.5
    )

    target_type = _text(target.get("property_type"))
    comp_type = _text(comp.get("property_type"))
    if target_type == comp_type:
        type_score = 1.0
    elif {target_type, comp_type} == {"apartment", "townhouse"}:
        type_score = 0.45
    else:
        type_score = 0.2

    target_sqft = _number(target.get("sqft"))
    comp_sqft = _number(comp.get("sqft"))
    sqft_score = (
        max(0.0, 1.0 - abs(target_sqft - comp_sqft) / max(target_sqft, comp_sqft))
        if target_sqft and comp_sqft
        else 0.5
    )

    target_year = _number(target.get("year_built"))
    comp_year = _number(comp.get("year_built"))
    age_score = (
        max(0.0, 1.0 - abs(target_year - comp_year) / 50.0)
        if target_year and comp_year
        else 0.5
    )

    target_amenities = _amenities(target.get("amenities"))
    comp_amenities = _amenities(comp.get("amenities", comp.get("amenities_json")))
    amenity_union = target_amenities | comp_amenities
    amenity_score = (
        len(target_amenities & comp_amenities) / len(amenity_union) if amenity_union else 0.5
    )

    observed = _day(comp.get("observed_on"))
    age_days = max(0, (as_of - observed).days) if observed else 1095
    recency_score = 1.0 / (1.0 + age_days / 365.0)

    return round(
        0.22 * city
        + 0.10 * neighborhood
        + 0.05 * zip_score
        + 0.18 * bed_score
        + 0.08 * bath_score
        + 0.16 * type_score
        + 0.10 * sqft_score
        + 0.05 * age_score
        + 0.03 * amenity_score
        + 0.03 * recency_score,
        6,
    )


def _adjustment_factors(
    target: dict[str, Any], comp: dict[str, Any]
) -> list[tuple[str, float]]:
    target_beds = _number(target.get("bedrooms")) or 0.0
    comp_beds = _number(comp.get("bedrooms")) or 0.0
    factors: list[tuple[str, float]] = [
        ("bedrooms", _bounded_ratio(1.0 + 0.11 * (target_beds - comp_beds), 0.78, 1.22))
    ]

    target_baths = _number(target.get("bathrooms"))
    comp_baths = _number(comp.get("bathrooms"))
    if target_baths is not None and comp_baths is not None:
        factors.append(
            (
                "bathrooms",
                _bounded_ratio(1.0 + 0.045 * (target_baths - comp_baths), 0.91, 1.09),
            )
        )

    target_type = _text(target.get("property_type"))
    comp_type = _text(comp.get("property_type"))
    type_ratio = PROPERTY_TYPE_FACTORS[target_type] / PROPERTY_TYPE_FACTORS[comp_type]
    factors.append(("property_type", type_ratio))

    target_sqft = _number(target.get("sqft"))
    comp_sqft = _number(comp.get("sqft"))
    if target_sqft and comp_sqft:
        factors.append(("sqft", _bounded_ratio((target_sqft / comp_sqft) ** 0.32, 0.80, 1.25)))

    target_year = _number(target.get("year_built"))
    comp_year = _number(comp.get("year_built"))
    if target_year and comp_year:
        factors.append(
            (
                "year_built",
                _bounded_ratio(1.0 + 0.0015 * (target_year - comp_year), 0.94, 1.06),
            )
        )

    target_amenities = _amenities(target.get("amenities"))
    comp_amenities = _amenities(comp.get("amenities", comp.get("amenities_json")))
    if target_amenities or comp_amenities:
        difference = len(target_amenities - comp_amenities) - len(
            comp_amenities - target_amenities
        )
        factors.append(("amenities", _bounded_ratio(1.0 + 0.015 * difference, 0.94, 1.06)))

    return factors


def _weighted_quantile(values: list[tuple[float, float]], quantile: float) -> float:
    ordered = sorted(values, key=lambda pair: pair[0])
    total = sum(weight for _, weight in ordered)
    threshold = total * quantile
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= threshold:
            return value
    return ordered[-1][0]


def _trim_extremes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) < 5:
        return rows
    center = median(row["adjusted_rent"] for row in rows)
    mad = median(abs(row["adjusted_rent"] - center) for row in rows)
    if mad == 0:
        return rows
    kept = [row for row in rows if abs(row["adjusted_rent"] - center) <= 3.5 * mad]
    return kept if len(kept) >= 3 else rows


def _confidence(
    rows: list[dict[str, Any]], target: dict[str, Any], as_of: date
) -> tuple[float, str]:
    if not rows:
        return 0.0, "none"
    count_score = min(len(rows), 8) / 8.0
    similarity_score = sum(row["similarity"] for row in rows) / len(rows)
    requested = ("neighborhood", "bathrooms", "sqft", "year_built", "amenities")
    known_target_fields = [field for field in requested if bool(target.get(field))]
    target_completeness = len(known_target_fields) / len(requested)
    comparable_coverage = (
        sum(
            bool(
                row.get(field)
                if field != "amenities"
                else _amenities(row.get("amenities", row.get("amenities_json")))
            )
            for row in rows
            for field in known_target_fields
        )
        / (len(rows) * len(known_target_fields))
        if known_target_fields
        else 0.0
    )
    # Attribute availability on both sides matters: a detailed subject cannot be
    # matched precisely against comparables whose corresponding facts are absent.
    completeness = (target_completeness + comparable_coverage) / 2.0
    freshness = sum(
        1.0 / (1.0 + max(0, (as_of - row["_observed_date"]).days) / 365.0)
        for row in rows
    ) / len(rows)
    score = min(
        1.0,
        0.40 * count_score
        + 0.35 * similarity_score
        + 0.15 * completeness
        + 0.10 * freshness,
    )
    # A highly similar single observation is still only a single observation.
    # Evidence caps prevent feature completeness from overstating certainty.
    if len(rows) == 1:
        score = min(score, 0.45)
    elif len(rows) == 2:
        score = min(score, 0.55)
    score = round(score, 2)
    label = "high" if score >= 0.75 else "medium" if score >= 0.50 else "low"
    return score, label


def _empty_result(as_of: date) -> dict[str, Any]:
    return {
        "status": "no_data",
        "method": "comparable_adjustment_v1",
        "as_of": as_of.isoformat(),
        "estimate_monthly_rent": None,
        "range": None,
        "confidence": {"score": 0.0, "label": "none"},
        "sample_size": 0,
        "comparable_pool_size": 0,
        "adjustments": [],
        "comparables": [],
        "disclaimer": _disclaimer(),
    }


def _disclaimer() -> str:
    return (
        "Rule-based comparable analysis, not an appraisal or a machine-learning prediction. "
        "The range reflects available observations and may omit unrecorded property condition, "
        "upgrades, concessions, utilities, parking, lease terms, negotiation, incentives, market "
        "shifts, and other rent drivers."
    )


def estimate_rent(
    target: dict[str, Any],
    observations: Iterable[dict[str, Any]],
    *,
    as_of: date | str | None = None,
    max_comparables: int = 8,
) -> dict[str, Any]:
    """Estimate monthly rent using deterministic, bounded comparable adjustments."""

    raw_rows = [dict(row) for row in observations]
    parsed_dates = [_day(row.get("observed_on")) for row in raw_rows]
    effective_as_of = _day(as_of) or max(
        (item for item in parsed_dates if item),
        default=datetime.now(UTC).date(),
    )

    valid: list[dict[str, Any]] = []
    for row in raw_rows:
        rent = _number(row.get("monthly_rent"))
        observed = _day(row.get("observed_on"))
        property_type = _text(row.get("property_type"))
        bedrooms = _number(row.get("bedrooms"))
        if (
            rent is None
            or rent <= 0
            or observed is None
            or observed > effective_as_of
            or (effective_as_of - observed).days > 1096
            or property_type not in PROPERTY_TYPE_FACTORS
            or bedrooms is None
        ):
            continue
        row["monthly_rent"] = rent
        row["_observed_date"] = observed
        row["similarity"] = _feature_score(target, row, effective_as_of)
        valid.append(row)

    if not valid:
        return _empty_result(effective_as_of)

    target_city = _text(target.get("city"))
    same_city = [row for row in valid if _text(row.get("city")) == target_city]
    # Cross-city observations only backfill a genuinely sparse local pool.
    pool = same_city if len(same_city) >= 3 else valid
    pool.sort(
        key=lambda row: (
            -row["similarity"],
            -row["_observed_date"].toordinal(),
            str(row.get("observation_id") or ""),
        )
    )
    selected = pool[: max(1, min(max_comparables, 20))]

    adjusted: list[dict[str, Any]] = []
    factor_impacts: dict[str, list[tuple[float, float]]] = {}
    target_amenities = _amenities(target.get("amenities"))
    for row in selected:
        rent = row["monthly_rent"]
        observed = row["_observed_date"]
        age_days = max(0, (effective_as_of - observed).days)
        recency_weight = 1.0 / (1.0 + age_days / 365.0)
        weight = max(0.001, row["similarity"] ** 3 * recency_weight)
        running = rent
        for name, factor in _adjustment_factors(target, row):
            impact = running * (factor - 1.0)
            factor_impacts.setdefault(name, []).append((impact, weight))
            running *= factor
        running = rent * _bounded_ratio(running / rent, 0.65, 1.55)
        comp_amenities = _amenities(row.get("amenities", row.get("amenities_json")))
        adjusted.append(
            {
                **row,
                "adjusted_rent": running,
                "weight": weight,
                "matched_amenities": sorted(target_amenities & comp_amenities),
            }
        )

    adjusted = _trim_extremes(adjusted)
    weighted = [(row["adjusted_rent"], row["weight"]) for row in adjusted]
    estimate = _weighted_quantile(weighted, 0.50)
    confidence_score, confidence_label = _confidence(adjusted, target, effective_as_of)

    sample_half_width = (
        0.25 if len(adjusted) == 1 else 0.18 if len(adjusted) == 2 else 0.14
        if len(adjusted) <= 4
        else 0.10 if len(adjusted) <= 7 else 0.07
    )
    # The empirical quantiles capture observed dispersion.  This floor also
    # expands as evidence quality falls; it is a guardrail, not a calibrated
    # prediction interval or coverage guarantee.
    evidence_half_width = min(0.30, 0.06 + (1.0 - confidence_score) * 0.25)
    minimum_half_width = max(sample_half_width, evidence_half_width)
    lower = min(_weighted_quantile(weighted, 0.20), estimate * (1.0 - minimum_half_width))
    upper = max(_weighted_quantile(weighted, 0.80), estimate * (1.0 + minimum_half_width))

    descriptions = {
        "bedrooms": "Heuristic, bounded 11% adjustment per bedroom difference.",
        "bathrooms": "Heuristic, bounded 4.5% adjustment per bathroom difference.",
        "property_type": "Heuristic apartment, townhouse, and single-family type adjustment.",
        "sqft": "Heuristic size adjustment with damped square-footage scaling.",
        "year_built": "Small heuristic, capped adjustment for relative property age.",
        "amenities": "Small heuristic, capped adjustment for recorded amenity differences.",
    }
    adjustments = []
    for factor, description in descriptions.items():
        impacts = factor_impacts.get(factor)
        if not impacts:
            continue
        total_weight = sum(weight for _, weight in impacts)
        average_impact = sum(impact * weight for impact, weight in impacts) / total_weight
        adjustments.append(
            {
                "factor": factor,
                "impact_dollars": _round_rent(average_impact),
                "description": description,
            }
        )
    adjustments.extend(
        [
            {
                "factor": "location",
                "impact_dollars": 0.0,
                "description": "Same-city observations are preferred; neighborhood and ZIP affect ranking.",
            },
            {
                "factor": "recency",
                "impact_dollars": 0.0,
                "description": "Newer observations receive greater weight; records older than three years are excluded.",
            },
        ]
    )

    public_comparables = []
    for row in adjusted:
        public_comparables.append(
            {
                "observation_id": str(row.get("observation_id") or "unknown"),
                "observed_on": row["_observed_date"].isoformat(),
                "city": str(row.get("city") or ""),
                "neighborhood": row.get("neighborhood"),
                "monthly_rent": _round_rent(row["monthly_rent"]),
                "adjusted_rent": _round_rent(row["adjusted_rent"]),
                "similarity": round(row["similarity"], 2),
                "bedrooms": int(float(row["bedrooms"])),
                "bathrooms": _number(row.get("bathrooms")),
                "property_type": _text(row.get("property_type")),
                "sqft": _number(row.get("sqft")),
                "year_built": int(float(row["year_built"]))
                if _number(row.get("year_built")) is not None
                else None,
                "matched_amenities": row["matched_amenities"],
            }
        )

    return {
        "status": "estimated"
        if len(adjusted) >= 3 and confidence_score >= 0.50
        else "low_data",
        "method": "comparable_adjustment_v1",
        "as_of": effective_as_of.isoformat(),
        "estimate_monthly_rent": _round_rent(estimate),
        "range": {"low": _round_rent(lower), "high": _round_rent(upper)},
        "confidence": {"score": confidence_score, "label": confidence_label},
        "sample_size": len(adjusted),
        "comparable_pool_size": len(pool),
        "adjustments": adjustments,
        "comparables": public_comparables,
        "disclaimer": _disclaimer(),
    }
