"""Resolve published Agent A names without guessing payload keys.

Analysis modules A must ship:
  realtykit.analysis.correlation
  realtykit.analysis.dips
  realtykit.analysis.outliers
  realtykit.analysis.align
  realtykit.analysis.constants

Function names follow docs/research/01-architecture.md §7 plus the analyst
agent (pearson, stock_dips, outliers_geo, outliers_listing, align_weekly).
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

# --- constants (published) -------------------------------------------------

HIGH_PRICE_MULT = 2.5
LOW_PRICE_MULT = 0.4
HIGH_DOM_MULT = 3
MIN_CORRELATION_N = 12
DIP_NEAR_LOW_MAX = 0.05
DIP_DRAWDOWN_MAX = -0.20
STALE_HOURS = 168

_MESSAGE_KEYS = ("message", "disclaimer", "note", "copy", "warning", "caption")


def load_module(dotted: str):
    return importlib.import_module(dotted)


def first_attr(mod, names: Sequence[str], *, required: bool = True):
    for name in names:
        if hasattr(mod, name):
            return getattr(mod, name)
    if required:
        raise AttributeError(
            f"{mod.__name__} has none of {list(names)}; Agent A must export one"
        )
    return None


def first_callable(mod, names: Sequence[str]) -> Callable[..., Any]:
    for name in names:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    raise AttributeError(
        f"{mod.__name__} has no callable among {list(names)}; Agent A must export one"
    )


def call_flex(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call fn, dropping kwargs the signature does not accept."""
    sig = inspect.signature(fn)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return fn(*args, **kwargs)
    accepted = {
        name
        for name, p in sig.parameters.items()
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    }
    filtered = {k: v for k, v in kwargs.items() if k in accepted}
    return fn(*args, **filtered)


def as_mapping(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        return dict(obj)
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return dict(dump())
    as_dict = getattr(obj, "dict", None)
    if callable(as_dict) and not isinstance(obj, type):
        try:
            data = as_dict()
            if isinstance(data, Mapping):
                return dict(data)
        except TypeError:
            pass
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return {}


def as_rows(obj: Any) -> list[Any]:
    if obj is None:
        return []
    if isinstance(obj, Mapping) and "rows" in obj:
        return list(obj["rows"])
    if isinstance(obj, (list, tuple)):
        return list(obj)
    mapped = as_mapping(obj)
    if "rows" in mapped:
        return list(mapped["rows"])
    return [obj]


def field(obj: Any, *names: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        for name in names:
            if name in obj:
                return obj[name]
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    mapped = as_mapping(obj)
    for name in names:
        if name in mapped:
            return mapped[name]
    return default


def collect_messages(obj: Any) -> list[str]:
    texts: list[str] = []

    def walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            return
        if isinstance(node, Mapping):
            for key, val in node.items():
                if key in _MESSAGE_KEYS and isinstance(val, str) and val.strip():
                    texts.append(val)
                else:
                    walk(val)
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        mapped = as_mapping(node)
        if mapped:
            walk(mapped)

    walk(obj)
    return texts


def status_of(obj: Any) -> str | None:
    if isinstance(obj, str):
        return obj
    raw = field(obj, "status", "reason", "code", "freshness")
    if raw is None:
        return None
    if hasattr(raw, "value"):
        raw = raw.value
    return str(raw)


def truthy(obj: Any, *names: str) -> bool:
    val = field(obj, *names)
    return bool(val)


# --- analysis entry points -------------------------------------------------


def constants_mod():
    return load_module("realtykit.analysis.constants")


def correlation_mod():
    return load_module("realtykit.analysis.correlation")


def dips_mod():
    return load_module("realtykit.analysis.dips")


def outliers_mod():
    return load_module("realtykit.analysis.outliers")


def align_mod():
    return load_module("realtykit.analysis.align")


def pearson_fn():
    return first_callable(
        correlation_mod(),
        (
            "pearson",
            "pearson_r",
            "corr",
            "correlation_coefficient",
            "pearson_pairs",
        ),
    )


def correlate_fn():
    return first_callable(
        correlation_mod(),
        (
            "correlate",
            "correlation",
            "compute_correlation",
            "pearson_pair",
            "pearson_pairs",
        ),
    )


def dip_fn():
    return first_callable(
        dips_mod(),
        (
            "dip_metrics",
            "evaluate_dip",
            "flag_dip",
            "classify_dip",
            "is_dip",
            "stock_dip",
            "stock_dips",
        ),
    )


def outliers_geo_fn():
    return first_callable(
        outliers_mod(),
        (
            "metro_zscore_outliers",
            "outliers_geo",
            "metro_outliers",
            "geo_outliers",
            "zscore_outliers",
        ),
    )


def outliers_listing_fn():
    return first_callable(
        outliers_mod(),
        ("outliers_listing", "listing_outliers", "flag_listings"),
    )


def align_weekly_fn():
    return first_callable(align_mod(), ("align_weekly", "align", "align_series"))


def freshness_fn():
    """Classify a source / listing / city row. Dual-clock in, status out."""
    errors: list[str] = []
    for dotted in (
        "realtykit.freshness",
        "realtykit.models.freshness",
        "realtykit.analysis.freshness",
        "realtykit.ingest.freshness",
        "realtykit.store.sources",
    ):
        try:
            mod = load_module(dotted)
        except ImportError as exc:
            errors.append(f"{dotted}: {exc}")
            continue
        try:
            return first_callable(
                mod,
                (
                    "source_block",
                    "classify",
                    "classify_source",
                    "classify_freshness",
                    "evaluate_freshness",
                    "source_status",
                    "flag_stale",
                    "apply_freshness",
                    "build_freshness",
                ),
            )
        except AttributeError as exc:
            errors.append(str(exc))
    raise ImportError(
        "no freshness classifier found; Agent A must export "
        "classify_source (or alias) from models.freshness. "
        + " | ".join(errors)
    )


def listing_validator():
    try:
        mod = load_module("realtykit.models.listing")
        fn = first_attr(mod, ("validate_listing", "require_as_of"), required=False)
        if callable(fn):
            return fn
        model = first_attr(mod, ("Listing", "ListingRow"), required=False)
        if model is not None:
            return model
    except ImportError:
        pass
    try:
        mod = load_module("realtykit.models.freshness")
        fn = first_attr(
            mod, ("validate_listing", "require_listing_as_of", "require_as_of"), required=False
        )
        if callable(fn):
            return fn
    except ImportError:
        pass
    raise ImportError(
        "no listing validator; Agent A must reject listings without as_of "
        "(realtykit.models.listing.Listing or validate_listing)"
    )


def invoke_listing(validator: Any, payload: dict[str, Any]) -> Any:
    if inspect.isclass(validator):
        if hasattr(validator, "model_validate"):
            return validator.model_validate(payload)
        return validator(**payload)
    return call_flex(validator, payload)


def invoke_correlate(xs: Sequence[float], ys: Sequence[float]) -> Any:
    if len(xs) >= MIN_CORRELATION_N:
        try:
            coef = invoke_pearson(xs, ys)
            if coef is not None:
                return {
                    "pearson": coef,
                    "r": coef,
                    "n": len(xs),
                    "status": "ok",
                    "disclaimer": (
                        "Correlation is not causation. Aligned weekly observations "
                        "do not imply that housing, equities, or mortgage rates "
                        "cause each other."
                    ),
                }
        except TypeError:
            pass
    fn = correlate_fn()
    try:
        return call_flex(fn, xs, ys)
    except TypeError:
        try:
            return call_flex(fn, housing=xs, equity=ys, x=xs, y=ys)
        except TypeError:
            return call_flex(
                fn,
                housing=_dated_pairs(xs),
                equity=_dated_pairs(ys),
                mortgage=None,
            )


def _dated_pairs(xs: Sequence[float]) -> list[tuple[str, float]]:
    return [(f"2020-01-{i + 1:02d}", float(v)) for i, v in enumerate(xs)]


def invoke_pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    fn = pearson_fn()
    try:
        result = call_flex(fn, xs, ys)
    except TypeError:
        result = call_flex(
            fn,
            housing=_dated_pairs(xs),
            equity=_dated_pairs(ys),
            mortgage=None,
        )
    if isinstance(result, (int, float)):
        return float(result)
    val = field(result, "pearson", "r", "value")
    if val is None:
        pairs = field(result, "pairs") or []
        if pairs:
            val = field(pairs[0], "pearson", "r", "value")
    if val is None:
        raise TypeError(f"pearson() did not return a coefficient: {result!r}")
    return float(val)


def invoke_dip(*, price: float, low_52w: float, high_52w: float) -> Any:
    fn = dip_fn()
    attempts = (
        lambda: call_flex(fn, price, low_52w, high_52w),
        lambda: call_flex(fn, last=price, low_52w=low_52w, high_52w=high_52w),
        lambda: call_flex(
            fn,
            price=price,
            low_52w=low_52w,
            high_52w=high_52w,
            low=low_52w,
            high=high_52w,
            last=price,
            close=price,
        ),
        lambda: call_flex(
            fn,
            {
                "price": price,
                "close": price,
                "low_52w": low_52w,
                "high_52w": high_52w,
                "pct_above_52w_low": (price - low_52w) / low_52w if low_52w else None,
                "drawdown_52w": (price - high_52w) / high_52w if high_52w else None,
            },
        ),
    )
    last_err: Exception | None = None
    for attempt in attempts:
        try:
            return attempt()
        except TypeError as exc:
            last_err = exc
    if last_err:
        raise last_err
    raise TypeError("dip function rejected all contract call shapes")


def invoke_outliers_geo(rows: Iterable[Mapping[str, Any]]) -> Any:
    fn = outliers_geo_fn()
    material = list(rows)
    values = [float(r["value"]) for r in material]
    attempts = (
        lambda: call_flex(fn, material),
        lambda: call_flex(fn, material, metric="value"),
        lambda: call_flex(
            fn, rows=material, metros=material, values=values, metric="value"
        ),
        lambda: call_flex(fn, values),
    )
    last_err: Exception | None = None
    for attempt in attempts:
        try:
            return attempt()
        except TypeError as exc:
            last_err = exc
    if last_err:
        raise last_err
    raise TypeError("outliers_geo rejected all contract call shapes")


def invoke_outliers_listing(
    listings: Sequence[Mapping[str, Any]],
    *,
    median_price: float,
    median_dom: float | None,
    as_of: str | None = None,
    source: str | None = None,
) -> Any:
    fn = outliers_listing_fn()
    attempts = (
        lambda: call_flex(
            fn,
            listings,
            median_price,
            median_dom,
        ),
        lambda: call_flex(
            fn,
            listings,
            city_median_price=median_price,
            city_median_dom=median_dom,
            median_price=median_price,
            median_dom=median_dom,
            as_of=as_of,
            source=source,
        ),
        lambda: call_flex(
            fn,
            listings=listings,
            city_median=median_price,
            median_price=median_price,
            median_dom=median_dom,
        ),
    )
    last_err: Exception | None = None
    for attempt in attempts:
        try:
            return attempt()
        except TypeError as exc:
            last_err = exc
    if last_err:
        raise last_err
    raise TypeError("outliers_listing rejected all contract call shapes")


def invoke_freshness(row: Mapping[str, Any], now) -> Any:
    fn = freshness_fn()
    payload = dict(row)

    def _from_classify_tuple(result: Any) -> Any:
        if isinstance(result, tuple) and len(result) >= 1:
            status = result[0]
            hours = result[1] if len(result) > 1 else None
            stale = str(status) in {"stale", "aging", "unavailable"}
            return {
                "status": status,
                "freshness_hours": hours,
                "stale": stale,
                "observation_as_of": payload.get("observation_as_of"),
                "http_last_modified": payload.get("http_last_modified"),
            }
        return result

    attempts = (
        lambda: call_flex(fn, payload),
        lambda: call_flex(
            fn,
            observation_as_of=payload.get("observation_as_of"),
            cadence=payload.get("cadence") or "weekly",
            http_last_modified=payload.get("http_last_modified"),
        ),
        lambda: call_flex(fn, payload, now=now),
        lambda: call_flex(fn, payload, now),
        lambda: call_flex(fn, **payload, now=now),
        lambda: call_flex(fn, [payload], now=now),
    )
    last_err: Exception | None = None
    for attempt in attempts:
        try:
            result = attempt()
            if isinstance(result, list) and result:
                return _from_classify_tuple(result[0])
            return _from_classify_tuple(result)
        except TypeError as exc:
            last_err = exc
    if last_err:
        raise last_err
    raise TypeError("freshness classifier rejected all contract call shapes")


def is_stale(result: Any) -> bool:
    flag = field(result, "stale")
    if flag is not None:
        return bool(flag)
    status = (status_of(result) or "").lower()
    return status == "stale"


def is_dip(result: Any) -> bool:
    if isinstance(result, bool):
        return result
    if isinstance(result, Mapping) and "dips" in result:
        dips = result["dips"]
        if isinstance(dips, Sequence) and not isinstance(dips, (str, bytes)):
            return len(dips) > 0
    flag = field(result, "dip", "is_dip", "flagged")
    if flag is not None:
        return bool(flag)
    raise AssertionError(f"dip result has no dip flag: {result!r}")
