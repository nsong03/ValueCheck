"""DCF assumptions — every lever, in one editable place.

Lifted from the validated seed core (seed/engine.py). Defaults are seeded from
the company's own history by `Assumptions.seed_from()` but are meant to be
overridden by the analyst; the engine treats them as explicit inputs, never
guesses.
"""

from __future__ import annotations

from dataclasses import dataclass

from equity.domain import metrics
from equity.domain.models import CompanyFinancials


@dataclass(slots=True)
class Assumptions:
    """Every DCF lever. Mutable by design: the analyst edits these."""

    horizon: int = 5  # explicit projection years
    rev_growth: float = 0.06  # annual revenue growth (yr 1..N)
    rev_growth_terminal: float = 0.03  # growth in final projected year (fades to this)
    ebit_margin: float = 0.28  # target operating margin
    tax_rate: float = 0.15
    da_pct_rev: float = 0.03  # D&A as % of revenue
    capex_pct_rev: float = 0.03  # capex as % of revenue
    nwc_pct_rev: float = 0.01  # incremental NWC as % of revenue change

    # WACC components
    risk_free: float = 0.043
    equity_premium: float = 0.05
    beta: float = 1.0
    cost_of_debt: float = 0.045
    target_debt_weight: float = 0.15  # D / (D+E)

    terminal_growth: float = 0.025  # perpetuity growth g

    @classmethod
    def seed_from(cls, fin: CompanyFinancials, horizon: int = 5) -> Assumptions:
        """Sensible starting point derived from the company's own history.

        Behavior preserved verbatim from the seed engine, including the
        deliberate quirks:
        - revenue growth is clamped to [0%, 15%] before rounding;
        - a zero average EBIT margin falls back to 20% (`or 0.20`);
        - missing tax/D&A/capex history falls back to the class defaults.
        """
        g = fin.revenue_cagr()
        return cls(
            horizon=horizon,
            rev_growth=round(min(max(g, 0.0), 0.15), 4),
            rev_growth_terminal=0.03,
            ebit_margin=round(fin.avg_ebit_margin(), 4) or 0.20,
            tax_rate=(
                round(metrics.mean_or(fin.tax_rate, 0.15), 4)
                if len(fin.tax_rate.dropna())
                else 0.15
            ),
            da_pct_rev=(
                round(metrics.average_ratio(fin.da, fin.revenue), 4)
                if len(fin.da.dropna())
                else 0.03
            ),
            capex_pct_rev=(
                round(metrics.average_ratio(fin.capex, fin.revenue), 4)
                if len(fin.capex.dropna())
                else 0.03
            ),
            beta=fin.beta or 1.0,
        )
