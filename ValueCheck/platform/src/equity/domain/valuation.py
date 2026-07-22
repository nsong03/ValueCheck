"""Valuation result value objects.

`DCFResult` exposes every intermediate so the analyst verifies a *range and
its drivers*, not a black-box point estimate. Shape lifted from the seed
engine and locked by BUILD_SPEC §5.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from equity.domain.assumptions import Assumptions
from equity.domain.models import CompanyFinancials


@dataclass(frozen=True, slots=True)
class DCFResult:
    """Complete output of one DCF run.

    `projection` is the year-by-year FCFF build (revenue -> fcff -> pv_fcff),
    indexed by projection year 1..N. Monetary values in $M; `upside` is a
    fraction vs. the current price. `warnings` MUST contain an entry when
    terminal growth >= WACC and when the terminal value exceeds 75% of EV
    (BUILD_SPEC §5).
    """

    projection: pd.DataFrame
    wacc: float
    enterprise_value: float
    equity_value: float
    fair_value_per_share: float
    upside: float  # vs current price, as fraction
    assumptions: Assumptions
    fin: CompanyFinancials
    warnings: list[str] = field(default_factory=list)
