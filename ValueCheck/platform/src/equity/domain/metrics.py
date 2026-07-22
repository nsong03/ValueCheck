"""Core ratio metrics over fiscal-year series. Pure functions, no I/O.

These are the primitive calculations shared by the financial model
(`models.CompanyFinancials`) and assumption seeding (`assumptions.seed_from`).
Semantics are lifted verbatim from the validated seed core (seed/data.py):
degenerate inputs (empty series, non-positive base) return the documented
defaults rather than raising, because missing history is a normal condition
for thinly-filed companies.
"""

from __future__ import annotations

import pandas as pd


def cagr(series: pd.Series[float]) -> float:
    """Compound annual growth rate over a fiscal-year series.

    Returns 0.0 when there are fewer than two observations or the first
    observation is non-positive (growth is undefined) — seed behavior.
    """
    r = series.dropna()
    if len(r) < 2 or float(r.iloc[0]) <= 0:
        return 0.0
    n = len(r) - 1
    return float((r.iloc[-1] / r.iloc[0]) ** (1 / n) - 1)


def average_ratio(numerator: pd.Series[float], denominator: pd.Series[float]) -> float:
    """Mean of the element-wise ratio of two aligned series (NaNs dropped).

    Returns 0.0 when no year has both values — seed behavior
    (`avg_ebit_margin` on an empty history is 0.0, not an error).
    """
    m = (numerator / denominator).dropna()
    return float(m.mean()) if len(m) else 0.0


def mean_or(series: pd.Series[float], default: float) -> float:
    """Mean of a series with NaNs dropped, or `default` when empty."""
    s = series.dropna()
    return float(s.mean()) if len(s) else default
