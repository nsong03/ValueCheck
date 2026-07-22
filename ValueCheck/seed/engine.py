"""
engine.py — Deterministic DCF valuation. No LLM, no guessing: every number
is either pulled from filings or an explicit, editable assumption.

Method: unlevered free cash flow to the firm (FCFF), discounted at WACC,
Gordon-growth terminal value, then bridge from enterprise to equity value
per share. Every intermediate is exposed so you verify a *range and its
drivers*, not a black-box point estimate.

    FCFF = EBIT*(1-tax) + D&A - Capex - ΔNWC
    EV   = Σ FCFF_t / (1+WACC)^t  +  TV / (1+WACC)^N
    TV   = FCFF_N*(1+g) / (WACC - g)
    Equity = EV - NetDebt ;  per share = Equity / shares
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd

from data import CompanyFinancials


@dataclass
class Assumptions:
    """Every DCF lever, in one editable place. Defaults are seeded from the
    company's own history by `Assumptions.seed_from()` but are meant to be
    overridden by you."""
    horizon: int = 5                    # explicit projection years
    rev_growth: float = 0.06            # annual revenue growth (yr 1..N)
    rev_growth_terminal: float = 0.03   # growth in final projected year (fades to this)
    ebit_margin: float = 0.28           # target operating margin
    tax_rate: float = 0.15
    da_pct_rev: float = 0.03            # D&A as % of revenue
    capex_pct_rev: float = 0.03         # capex as % of revenue
    nwc_pct_rev: float = 0.01           # incremental NWC as % of revenue change

    # WACC components
    risk_free: float = 0.043
    equity_premium: float = 0.05
    beta: float = 1.0
    cost_of_debt: float = 0.045
    target_debt_weight: float = 0.15    # D / (D+E)

    terminal_growth: float = 0.025      # perpetuity growth g

    @classmethod
    def seed_from(cls, fin: CompanyFinancials, horizon: int = 5) -> "Assumptions":
        """Sensible starting point derived from the company's own history."""
        g = fin.revenue_cagr()
        return cls(
            horizon=horizon,
            rev_growth=round(min(max(g, 0.0), 0.15), 4),
            rev_growth_terminal=0.03,
            ebit_margin=round(fin.avg_ebit_margin(), 4) or 0.20,
            tax_rate=round(float(fin.tax_rate.dropna().mean()), 4) if len(fin.tax_rate.dropna()) else 0.15,
            da_pct_rev=round(float((fin.da / fin.revenue).dropna().mean()), 4) if len(fin.da.dropna()) else 0.03,
            capex_pct_rev=round(float((fin.capex / fin.revenue).dropna().mean()), 4) if len(fin.capex.dropna()) else 0.03,
            beta=fin.beta or 1.0,
        )


@dataclass
class DCFResult:
    projection: pd.DataFrame
    wacc: float
    enterprise_value: float
    equity_value: float
    fair_value_per_share: float
    upside: float                       # vs current price, as fraction
    assumptions: Assumptions
    fin: CompanyFinancials
    warnings: list[str] = field(default_factory=list)


class DCF:
    def __init__(self, fin: CompanyFinancials, a: Optional[Assumptions] = None):
        self.fin = fin
        self.a = a or Assumptions.seed_from(fin)

    # -- WACC ---------------------------------------------------------------
    def wacc(self) -> float:
        a = self.a
        cost_equity = a.risk_free + a.beta * a.equity_premium
        we = 1 - a.target_debt_weight
        wd = a.target_debt_weight
        after_tax_kd = a.cost_of_debt * (1 - a.tax_rate)
        return we * cost_equity + wd * after_tax_kd

    # -- projection ---------------------------------------------------------
    def project(self) -> pd.DataFrame:
        a = self.a
        rev0 = float(self.fin.revenue.iloc[-1])
        rows = []
        rev_prev = rev0
        # linearly fade growth from rev_growth -> rev_growth_terminal
        growth_path = np.linspace(a.rev_growth, a.rev_growth_terminal, a.horizon)
        for t in range(1, a.horizon + 1):
            g = growth_path[t - 1]
            rev = rev_prev * (1 + g)
            ebit = rev * a.ebit_margin
            nopat = ebit * (1 - a.tax_rate)
            da = rev * a.da_pct_rev
            capex = rev * a.capex_pct_rev
            d_nwc = (rev - rev_prev) * a.nwc_pct_rev
            fcff = nopat + da - capex - d_nwc
            rows.append({
                "year": t, "revenue": rev, "growth": g, "ebit": ebit,
                "nopat": nopat, "da": da, "capex": capex, "d_nwc": d_nwc,
                "fcff": fcff,
            })
            rev_prev = rev
        df = pd.DataFrame(rows).set_index("year")
        w = self.wacc()
        df["discount"] = [(1 + w) ** t for t in df.index]
        df["pv_fcff"] = df["fcff"] / df["discount"]
        return df

    # -- valuation ----------------------------------------------------------
    def value(self) -> DCFResult:
        a = self.a
        warnings = []
        w = self.wacc()
        if a.terminal_growth >= w:
            warnings.append(
                f"terminal growth ({a.terminal_growth:.1%}) >= WACC ({w:.1%}); "
                "terminal value is invalid. Lower g or raise WACC.")
        proj = self.project()

        fcff_n = float(proj["fcff"].iloc[-1])
        tv = fcff_n * (1 + a.terminal_growth) / (w - a.terminal_growth) if w > a.terminal_growth else float("nan")
        pv_tv = tv / ((1 + w) ** a.horizon)

        ev = float(proj["pv_fcff"].sum()) + pv_tv
        equity = ev - self.fin.net_debt
        per_share = equity / self.fin.shares_out if self.fin.shares_out else float("nan")
        upside = (per_share / self.fin.price - 1) if self.fin.price else float("nan")

        tv_share = pv_tv / ev if ev else float("nan")
        if tv_share > 0.75:
            warnings.append(
                f"terminal value is {tv_share:.0%} of EV — result is highly "
                "sensitive to g and WACC. Lengthen horizon or sanity-check terminal.")

        return DCFResult(
            projection=proj, wacc=w, enterprise_value=ev, equity_value=equity,
            fair_value_per_share=per_share, upside=upside,
            assumptions=a, fin=self.fin, warnings=warnings,
        )

    # -- sensitivity --------------------------------------------------------
    def sensitivity(self, wacc_delta=0.01, g_delta=0.005, n=5) -> pd.DataFrame:
        """Fair-value-per-share grid over WACC (rows) x terminal growth (cols).
        This IS the deliverable — a range and its drivers, not one number."""
        base_w = self.wacc()
        base_g = self.a.terminal_growth
        k = n // 2
        waccs = [base_w + (i - k) * wacc_delta for i in range(n)]
        gs = [base_g + (j - k) * g_delta for j in range(n)]

        grid = np.full((n, n), np.nan)
        orig = self.a
        for i, wv in enumerate(waccs):
            for j, gv in enumerate(gs):
                # solve implied beta so wacc() returns wv, holding structure fixed
                a2 = Assumptions(**{**orig.__dict__})
                a2.terminal_growth = gv
                # back out beta to hit target wacc wv:
                we = 1 - a2.target_debt_weight
                after_tax_kd = a2.cost_of_debt * (1 - a2.tax_rate)
                ke_needed = (wv - a2.target_debt_weight * after_tax_kd) / we
                a2.beta = (ke_needed - a2.risk_free) / a2.equity_premium
                res = DCF(self.fin, a2).value()
                grid[i, j] = res.fair_value_per_share
        self.a = orig
        return pd.DataFrame(
            grid,
            index=[f"WACC {x:.1%}" for x in waccs],
            columns=[f"g {x:.2%}" for x in gs],
        ).round(2)
