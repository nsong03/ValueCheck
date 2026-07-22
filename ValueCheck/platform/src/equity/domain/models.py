"""Normalized financial data model — the ONE shape the rest of the app depends on.

Lifted from the validated seed core (seed/data.py). The DCF engine downstream
only ever sees a `CompanyFinancials`, so it is completely decoupled from where
the numbers came from (EDGAR, market provider, fixture). Swap the source, keep
the engine.

Pure domain: no I/O, no imports from outer layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from equity.domain import metrics


def _empty_series() -> pd.Series[float]:
    return pd.Series(dtype=float)


@dataclass(frozen=True, slots=True)
class SourceLink:
    """A verifiable pointer back to the original document for one datum.

    Every external number carries one of these (CLAUDE.md prime directive #4):
    a filing datum links to the SEC document, a market datum to its provider.
    """

    label: str  # e.g. "10-K FY2023"
    url: str  # direct SEC document URL
    accession: str  # SEC accession number (or provider id for market data)

    def __str__(self) -> str:
        return f"{self.label} <{self.url}>"


@dataclass(slots=True)
class CompanyFinancials:
    """Normalized, comparable financials for one company.

    Every series is indexed by fiscal year (int), oldest -> newest.
    All monetary values in millions USD; shares in millions. This normalization
    is what makes hundreds of companies comparable despite each tagging its
    XBRL differently.

    Mutable by design: the market-data enrichment step (Phase 2) fills the
    capital-structure fields in place after the filings load.
    """

    ticker: str
    name: str
    sector: str
    industry: str
    sic: str | None = None

    # Income statement
    revenue: pd.Series[float] = field(default_factory=_empty_series)
    ebit: pd.Series[float] = field(default_factory=_empty_series)  # operating income
    da: pd.Series[float] = field(default_factory=_empty_series)  # depreciation & amort.
    tax_rate: pd.Series[float] = field(default_factory=_empty_series)  # effective, fraction

    # Cash flow / balance sheet drivers
    capex: pd.Series[float] = field(default_factory=_empty_series)  # positive = spend
    nwc: pd.Series[float] = field(default_factory=_empty_series)  # net working capital

    # Capital structure (most recent)
    total_debt: float = 0.0
    cash: float = 0.0
    shares_out: float = 0.0  # millions
    price: float = 0.0  # current share price
    beta: float = 1.0

    sources: list[SourceLink] = field(default_factory=list)

    # ---- derived helpers ----------------------------------------------------
    @property
    def years(self) -> list[int]:
        return [int(y) for y in self.revenue.index]

    @property
    def net_debt(self) -> float:
        return self.total_debt - self.cash

    @property
    def market_cap(self) -> float:
        return self.shares_out * self.price

    def revenue_cagr(self) -> float:
        """Compound annual revenue growth over the available history."""
        return metrics.cagr(self.revenue)

    def avg_ebit_margin(self) -> float:
        """Mean EBIT margin over years where both EBIT and revenue exist."""
        return metrics.average_ratio(self.ebit, self.revenue)

    def historicals_table(self) -> pd.DataFrame:
        """Human-readable historicals summary (rounded), for display layers."""
        df = pd.DataFrame(
            {
                "Revenue": self.revenue,
                "EBIT": self.ebit,
                "EBIT margin": (self.ebit / self.revenue),
                "D&A": self.da,
                "Capex": self.capex,
                "NWC": self.nwc,
                "Tax rate": self.tax_rate,
            }
        )
        return df.round(3)
