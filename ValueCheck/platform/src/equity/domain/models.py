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
class MarketSnapshot:
    """Point-in-time capital-structure data from a market provider.

    All monetary values in millions USD to match `CompanyFinancials`; shares
    in millions. Lifted from the seed core (seed/market.py); `source_url` is
    new so the domain stays provider-agnostic — the adapter supplies the
    audit-trail URL instead of the domain hardcoding one.
    """

    price: float
    shares_out: float  # millions
    total_debt: float  # millions
    cash: float  # millions
    beta: float
    currency: str = "USD"
    as_of: str = ""  # ISO date
    provider: str = ""
    source_url: str = ""  # where a human can verify these numbers
    note: str = ""  # e.g. "beta defaulted to 1.0 (missing)"

    def is_complete(self) -> bool:
        """True when every field is present and not NaN (x == x filters NaN)."""
        return all(
            v is not None and v == v
            for v in (self.price, self.shares_out, self.total_debt, self.cash, self.beta)
        )


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

    # ---- market enrichment (pure: data in, mutation, no I/O) ----------------
    def apply_market_snapshot(self, snap: MarketSnapshot, overwrite: bool = False) -> None:
        """Populate capital-structure fields from a market snapshot.

        Only fills fields that are unset (0.0) unless `overwrite=True`, so a
        value deliberately entered by hand is preserved. Beta is special-cased:
        0.0/1.0 count as "unset" because 1.0 is the class default, not data.
        Appends a SourceLink so market inputs are as auditable as filings
        (seed/market.py `enrich`, minus the provider call — that I/O lives
        behind the MarketDataProvider port).
        """

        def maybe(attr: str, val: float) -> None:
            if overwrite or not getattr(self, attr):
                setattr(self, attr, val)

        maybe("price", snap.price)
        maybe("shares_out", snap.shares_out)
        maybe("total_debt", snap.total_debt)
        maybe("cash", snap.cash)
        if overwrite or self.beta in (0.0, 1.0):
            self.beta = snap.beta

        self.sources.append(
            SourceLink(
                label=f"Market data ({snap.provider}, {snap.as_of})",
                url=snap.source_url,
                accession=snap.provider,
            )
        )

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
