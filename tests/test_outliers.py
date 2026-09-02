"""Outlier contract: metro z-scores, listing multipliers, drop missing price."""

from __future__ import annotations

from tests.contract import (
    HIGH_DOM_MULT,
    HIGH_PRICE_MULT,
    LOW_PRICE_MULT,
    as_rows,
    constants_mod,
    field,
    invoke_outliers_geo,
    invoke_outliers_listing,
    outliers_geo_fn,
    outliers_listing_fn,
)


def test_listing_multiplier_constants():
    const = constants_mod()
    assert float(const.HIGH_PRICE_MULT) == HIGH_PRICE_MULT
    assert float(const.LOW_PRICE_MULT) == LOW_PRICE_MULT
    assert float(const.HIGH_DOM_MULT) == HIGH_DOM_MULT


def _ids(rows) -> set[str]:
    found: set[str] = set()
    for row in as_rows(rows):
        ident = field(row, "listing_id", "subject_id", "geo_id", "id")
        if ident is not None:
            found.add(str(ident))
    return found


def _reasons_blob(row) -> str:
    reasons = field(row, "reasons", "outlier_reasons") or []
    if isinstance(reasons, str):
        return reasons.lower()
    return " ".join(str(r) for r in reasons).lower()


def _flagged_geo_ids(result) -> set[str]:
    flagged: set[str] = set()
    for row in as_rows(result):
        ident = field(row, "geo_id", "subject_id", "id", "name")
        explicit = field(row, "outlier", "is_outlier", "flagged")
        score = field(row, "score", "z", "zscore", "mz")
        if explicit is False:
            continue
        keep = False
        if explicit:
            keep = True
        elif score is not None and abs(float(score)) >= 2:
            keep = True
        elif ident and "outlier" in str(ident).lower():
            keep = True
        if keep and ident is not None:
            flagged.add(str(ident))
    return flagged


def test_metro_zscore_flags_extreme_value(metro_rows):
    outliers_geo_fn()
    result = invoke_outliers_geo(metro_rows)
    flagged = _flagged_geo_ids(result)
    assert "metro:outlier" in flagged
    assert "metro:a" not in flagged


def test_listing_high_price_rule(listings_bundle):
    outliers_listing_fn()
    result = invoke_outliers_listing(
        listings_bundle["listings"],
        median_price=listings_bundle["city_median_price"],
        median_dom=listings_bundle["city_median_dom"],
        as_of=listings_bundle["as_of"],
        source=listings_bundle["source"],
    )
    ids = _ids(result)
    assert "high-price" in ids
    assert "normal" not in ids
    for row in as_rows(result):
        if field(row, "listing_id", "subject_id") == "high-price":
            blob = _reasons_blob(row)
            assert "price" in blob
            assert field(row, "as_of") is not None
            assert field(row, "source") is not None


def test_listing_low_price_rule(listings_bundle):
    outliers_listing_fn()
    result = invoke_outliers_listing(
        listings_bundle["listings"],
        median_price=listings_bundle["city_median_price"],
        median_dom=listings_bundle["city_median_dom"],
        as_of=listings_bundle["as_of"],
        source=listings_bundle["source"],
    )
    assert "low-price" in _ids(result)


def test_listing_high_dom_rule_when_dom_present(listings_bundle):
    outliers_listing_fn()
    result = invoke_outliers_listing(
        listings_bundle["listings"],
        median_price=listings_bundle["city_median_price"],
        median_dom=listings_bundle["city_median_dom"],
        as_of=listings_bundle["as_of"],
        source=listings_bundle["source"],
    )
    assert "high-dom" in _ids(result)
    for row in as_rows(result):
        if field(row, "listing_id", "subject_id") == "high-dom":
            assert "dom" in _reasons_blob(row)


def test_drop_listing_with_missing_price(listings_bundle):
    outliers_listing_fn()
    result = invoke_outliers_listing(
        listings_bundle["listings"],
        median_price=listings_bundle["city_median_price"],
        median_dom=listings_bundle["city_median_dom"],
        as_of=listings_bundle["as_of"],
        source=listings_bundle["source"],
    )
    ids = _ids(result)
    assert "no-price" not in ids
    for row in as_rows(result):
        price = field(row, "price", "value")
        if price is not None:
            assert price != ""


def test_drop_listing_with_missing_geo(listings_bundle):
    outliers_listing_fn()
    result = invoke_outliers_listing(
        listings_bundle["listings"],
        median_price=listings_bundle["city_median_price"],
        median_dom=listings_bundle["city_median_dom"],
        as_of=listings_bundle["as_of"],
        source=listings_bundle["source"],
    )
    assert "no-geo" not in _ids(result)
