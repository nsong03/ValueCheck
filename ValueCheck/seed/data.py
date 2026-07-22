"""
data.py — Financial data acquisition and normalization.

Two sources implement the same `CompanyFinancials` interface:

  1. EdgarSource   — pulls real XBRL from SEC EDGAR (runs on your machine).
  2. SyntheticSource — realistic hand-built data so the engine is testable
                       anywhere, including sandboxes that can't reach sec.gov.

The DCF engine downstream only ever sees a `CompanyFinancials` object, so it
is completely decoupled from where the numbers came from. Swap the source,
keep the engine.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


# ---------------------------------------------------------------------------
# Normalized schema — the ONE shape the rest of the app depends on.
# ---------------------------------------------------------------------------
@dataclass
class SourceLink:
    """A verifiable pointer back to the original filing for one datum."""
    label: str          # e.g. "10-K FY2023"
    url: str            # direct SEC document URL
    accession: str      # SEC accession number

    def __str__(self) -> str:
        return f"{self.label} <{self.url}>"


@dataclass
class CompanyFinancials:
    """
    Normalized, comparable financials for one company.

    Every series is indexed by fiscal year (int), oldest -> newest.
    All monetary values in millions USD. This normalization step is the
    part that makes hundreds of companies comparable despite each tagging
    its XBRL differently.
    """
    ticker: str
    name: str
    sector: str
    industry: str
    sic: Optional[str] = None

    # Income statement
    revenue: pd.Series = field(default_factory=pd.Series)
    ebit: pd.Series = field(default_factory=pd.Series)          # operating income
    da: pd.Series = field(default_factory=pd.Series)            # depreciation & amort.
    tax_rate: pd.Series = field(default_factory=pd.Series)      # effective, as fraction

    # Cash flow / balance sheet drivers
    capex: pd.Series = field(default_factory=pd.Series)         # positive = spend
    nwc: pd.Series = field(default_factory=pd.Series)           # net working capital

    # Capital structure (most recent)
    total_debt: float = 0.0
    cash: float = 0.0
    shares_out: float = 0.0                                     # millions
    price: float = 0.0                                          # current share price
    beta: float = 1.0

    sources: list[SourceLink] = field(default_factory=list)

    # ---- derived helpers -------------------------------------------------
    @property
    def years(self) -> list[int]:
        return list(self.revenue.index)

    @property
    def net_debt(self) -> float:
        return self.total_debt - self.cash

    @property
    def market_cap(self) -> float:
        return self.shares_out * self.price

    def revenue_cagr(self) -> float:
        r = self.revenue.dropna()
        if len(r) < 2 or r.iloc[0] <= 0:
            return 0.0
        n = len(r) - 1
        return (r.iloc[-1] / r.iloc[0]) ** (1 / n) - 1

    def avg_ebit_margin(self) -> float:
        m = (self.ebit / self.revenue).dropna()
        return float(m.mean()) if len(m) else 0.0

    def historicals_table(self) -> pd.DataFrame:
        df = pd.DataFrame({
            "Revenue": self.revenue,
            "EBIT": self.ebit,
            "EBIT margin": (self.ebit / self.revenue),
            "D&A": self.da,
            "Capex": self.capex,
            "NWC": self.nwc,
            "Tax rate": self.tax_rate,
        })
        return df.round(3)


# ---------------------------------------------------------------------------
# REAL source — runs on your machine (needs sec.gov reachable + identity).
# ---------------------------------------------------------------------------
class EdgarSource:
    """
    Live SEC XBRL via edgartools. This is the code path you'll actually use.

    Usage on your machine:
        import edgar
        edgar.set_identity("Your Name your@email.com")   # SEC requires this
        fin = EdgarSource().fetch("AAPL", years=5)

    XBRL concept names vary by filer, so we try a list of common tags for
    each line item and take the first that resolves — this is the core of
    the normalization work that makes companies comparable.
    """

    # Ordered fallbacks: US-GAAP concepts most filers use, best first.
    CONCEPTS = {
        "revenue":   ["RevenueFromContractWithCustomerExcludingAssessedTax",
                      "Revenues", "SalesRevenueNet"],
        "ebit":      ["OperatingIncomeLoss"],
        "da":        ["DepreciationDepletionAndAmortization",
                      "DepreciationAmortizationAndAccretionNet",
                      "DepreciationAndAmortization"],
        "capex":     ["PaymentsToAcquirePropertyPlantAndEquipment",
                      "PaymentsToAcquireProductiveAssets"],
        "pretax":    ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
        "tax":       ["IncomeTaxExpenseBenefit"],
    }

    def fetch(self, ticker: str, years: int = 5) -> CompanyFinancials:
        import edgar  # imported lazily so the module loads without network

        company = edgar.Company(ticker)
        facts = company.get_facts()  # XBRL facts object

        def series_for(keys):
            for k in keys:
                try:
                    s = facts.to_pandas(k)  # edgartools API varies by version;
                    if s is not None and len(s):
                        return s.tail(years)
                except Exception:
                    continue
            return pd.Series(dtype=float)

        rev = series_for(self.CONCEPTS["revenue"])
        ebit = series_for(self.CONCEPTS["ebit"])
        da = series_for(self.CONCEPTS["da"])
        capex = series_for(self.CONCEPTS["capex"]).abs()
        pretax = series_for(self.CONCEPTS["pretax"])
        tax = series_for(self.CONCEPTS["tax"])
        tax_rate = (tax / pretax).clip(0, 0.5) if len(pretax) else pd.Series(dtype=float)

        # Build source links from the most recent filings.
        sources = []
        try:
            for f in company.get_filings(form="10-K").head(years):
                sources.append(SourceLink(
                    label=f"10-K {f.filing_date}",
                    url=f.url if hasattr(f, "url") else "",
                    accession=str(getattr(f, "accession_no", "")),
                ))
        except Exception:
            pass

        return CompanyFinancials(
            ticker=ticker.upper(),
            name=getattr(company, "name", ticker),
            sector=getattr(company, "sector", "Unknown"),
            industry=getattr(company, "industry", "Unknown"),
            sic=str(getattr(company, "sic", "") or ""),
            revenue=rev, ebit=ebit, da=da, capex=capex, tax_rate=tax_rate,
            sources=sources,
        )
        # NOTE: capital-structure fields (debt/cash/shares/price/beta) come from
        # a market-data source (yfinance/OpenBB) on your machine; wired in the
        # app shell, omitted here to keep the core dependency-light.


# ---------------------------------------------------------------------------
# SYNTHETIC source — realistic data so the engine runs & is verifiable now.
# ---------------------------------------------------------------------------
class SyntheticSource:
    """Hand-built figures approximating a large-cap hardware company.
    Numbers are illustrative, not the real filings — they exist so you can
    see the engine's output quality without network access."""

    def fetch(self, ticker: str = "DEMO", years: int = 5) -> CompanyFinancials:
        yrs = list(range(2019, 2019 + years))
        idx = pd.Index(yrs, name="fiscal_year")
        rev = pd.Series([260174, 274515, 365817, 394328, 383285][:years], index=idx, dtype=float)
        ebit = pd.Series([63930, 66288, 108949, 119437, 114301][:years], index=idx, dtype=float)
        da = pd.Series([12547, 11056, 11284, 11104, 11519][:years], index=idx, dtype=float)
        capex = pd.Series([10495, 7309, 11085, 10708, 10959][:years], index=idx, dtype=float)
        nwc = pd.Series([-2500, -3100, -6200, -7400, -1900][:years], index=idx, dtype=float)
        tax = pd.Series([0.159, 0.144, 0.133, 0.162, 0.147][:years], index=idx, dtype=float)

        src = [SourceLink(f"10-K FY{y}",
                          f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=10-K&FY={y}",
                          f"0000320193-{y}-DEMO") for y in yrs]

        return CompanyFinancials(
            ticker=ticker, name="Demo Hardware Inc.",
            sector="Technology", industry="Consumer Electronics", sic="3571",
            revenue=rev, ebit=ebit, da=da, capex=capex, nwc=nwc, tax_rate=tax,
            total_debt=111088, cash=61555, shares_out=15550, price=195.0, beta=1.28,
            sources=src,
        )
