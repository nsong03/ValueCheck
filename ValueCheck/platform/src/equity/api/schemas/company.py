"""Company DTOs: summaries, historicals, and the source audit trail."""

from __future__ import annotations

import math

from pydantic import BaseModel

from equity.domain.models import CompanyFinancials, SourceLink


def none_if_nan(x: float) -> float | None:
    """JSON has no NaN; absent-because-incomputable becomes null."""
    return None if math.isnan(x) else x


class SourceLinkOut(BaseModel):
    label: str
    url: str
    accession: str

    @classmethod
    def from_domain(cls, s: SourceLink) -> SourceLinkOut:
        return cls(label=s.label, url=s.url, accession=s.accession)


class HistoricalsRow(BaseModel):
    """One fiscal year of normalized history ($M; tax_rate as fraction)."""

    fiscal_year: int
    revenue: float | None = None
    ebit: float | None = None
    da: float | None = None
    capex: float | None = None
    nwc: float | None = None
    tax_rate: float | None = None


class CompanySummary(BaseModel):
    ticker: str
    name: str
    sector: str
    industry: str
    sic: str | None
    price: float
    shares_out: float
    market_cap: float
    net_debt: float
    beta: float

    @classmethod
    def from_domain(cls, fin: CompanyFinancials) -> CompanySummary:
        return cls(
            ticker=fin.ticker,
            name=fin.name,
            sector=fin.sector,
            industry=fin.industry,
            sic=fin.sic,
            price=fin.price,
            shares_out=fin.shares_out,
            market_cap=fin.market_cap,
            net_debt=fin.net_debt,
            beta=fin.beta,
        )


class CompanyDetail(CompanySummary):
    historicals: list[HistoricalsRow]
    revenue_cagr: float
    avg_ebit_margin: float
    sources: list[SourceLinkOut]

    @classmethod
    def from_domain(cls, fin: CompanyFinancials) -> CompanyDetail:
        summary = CompanySummary.from_domain(fin)
        metrics = ("revenue", "ebit", "da", "capex", "nwc", "tax_rate")
        years: set[int] = set()
        for metric in metrics:
            years.update(int(y) for y in getattr(fin, metric).index)

        def cell(metric: str, year: int) -> float | None:
            series = getattr(fin, metric)
            if year not in series.index:
                return None
            return none_if_nan(float(series.loc[year]))

        rows = [
            HistoricalsRow(
                fiscal_year=year,
                **{m: cell(m, year) for m in metrics},
            )
            for year in sorted(years)
        ]
        return cls(
            **summary.model_dump(),
            historicals=rows,
            revenue_cagr=fin.revenue_cagr(),
            avg_ebit_margin=fin.avg_ebit_margin(),
            sources=[SourceLinkOut.from_domain(s) for s in fin.sources],
        )


class CompanyListOut(BaseModel):
    tickers: list[str]
