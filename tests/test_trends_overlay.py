from __future__ import annotations

from realtykit.api.routes import trends as trends_route


def test_combined_trends_keep_monthly_zhvi_and_all_requested_series(monkeypatch):
    fact_calls: list[tuple[str, str | None]] = []

    def fake_series_for(_geo_id, metric, **kwargs):
        fact_calls.append((metric, kwargs.get("cadence")))
        return [("2026-06-30", 100.0), ("2026-07-31", 105.0)]

    def fake_macro_series(series_id, **_kwargs):
        return [("2026-06-30", 200.0), ("2026-07-31", 210.0)] if series_id else []

    monkeypatch.setattr(trends_route, "series_for", fake_series_for)
    monkeypatch.setattr(trends_route, "macro_series", fake_macro_series)
    monkeypatch.setattr(
        trends_route,
        "_freshness",
        lambda _names: {
            "computed_at": "2026-09-07T00:00:00Z",
            "source": "test",
        },
    )

    result = trends_route.trends(
        geo_id="nation:US",
        metrics="inventory,days_on_market,new_listings,zhvi,median_list_price,gspc,mortgage_30y",
        cadence="weekly",
        from_date=None,
        to_date=None,
        _ok=None,
    )

    assert set(result.series) == {
        "inventory",
        "days_on_market",
        "new_listings",
        "zhvi",
        "median_list_price",
        "gspc",
        "mortgage_30y",
    }
    assert ("zhvi", "monthly") in fact_calls
    assert ("inventory", "weekly") in fact_calls
    assert len(result.series["zhvi"]) == 2
