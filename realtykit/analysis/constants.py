"""Single constants module. Routers must not invent magic numbers."""

# Correlation
MIN_CORRELATION_N = 12
DEFAULT_WINDOW_WEEKS = 104
DEFAULT_MAX_LAG = 0

# Stock dips (document in docs/metrics.md)
DIP_PCT_ABOVE_52W_LOW = 0.05  # dip if last close is ≤ 5% above 52-week low
DIP_DRAWDOWN_FROM_HIGH = -0.20  # dip if drawdown from 52-week high is ≤ −20%

# Metro / market outliers (no listings in no-key MVP)
OUTLIER_Z_ABS = 2.0
OUTLIER_METRICS = ("inventory_wow", "days_on_market", "zhvi_mom")

# Listing outliers (RentCast / MLS only — unused until listings exist)
HIGH_PRICE_MULT = 2.5
LOW_PRICE_MULT = 0.4
HIGH_DOM_MULT = 3.0

# Freshness (hours)
LIVE_HOURS = 24.0
FRESH_HOURS = 7 * 24.0
AGING_HOURS = 14 * 24.0
LISTING_SLA_HOURS = 168.0

DISCLAIMER = (
    "Correlation is not causation. Aligned weekly observations do not imply "
    "that housing, equities, or mortgage rates cause each other."
)
