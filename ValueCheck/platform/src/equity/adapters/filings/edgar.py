"""SEC EDGAR filings adapter (edgartools) — the live FilingsProvider.

Ported from the seed prototype (seed/data.py EdgarSource) and adapted to the
REAL edgartools 5.x API, which the sandboxed prototype could never exercise:

- `facts.to_pandas(concept)` does not exist; the working recipe is
  `facts.query().by_concept(c).by_fiscal_period("FY").by_period_length(12)`.
- The facts `fiscal_year` column is the *filing's* FY, not the period's year,
  so series are indexed by the year of `period_end`.
- 10-K filings restate prior years, so periods repeat across filings; we keep
  the most recently filed value per period.
- Facts arrive in absolute dollars; `CompanyFinancials` is in $millions
  (BUILD_SPEC §5), so values are scaled here.

The SEC requires an identifying User-Agent (fair access); it is injected via
constructor from Settings — never hardcoded.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from equity.adapters.filings.concepts import CONCEPTS
from equity.domain.models import CompanyFinancials, SourceLink
from equity.errors import ErrorCode, UpstreamError
from equity.logging import get_logger

log = get_logger(__name__)

_MM = 1_000_000.0


class EdgarFilingsSource:
    """Live SEC XBRL via edgartools. Implements ports.filings.FilingsProvider."""

    def __init__(self, identity: str | None) -> None:
        # Validation happens at fetch time, not construction: the composition
        # root must be buildable without an identity so cached companies keep
        # working fully offline (cache-first, BUILD_SPEC Phase 4).
        self._identity = (identity or "").strip()

    def fetch(self, ticker: str, years: int = 5) -> CompanyFinancials:
        if not self._identity:
            raise UpstreamError(
                "SEC EDGAR requires an identity (set EQUITY_EDGAR_IDENTITY, "
                'e.g. "Jane Doe jane@example.com")',
                code=ErrorCode.FILINGS_UNAVAILABLE,
            )
        import edgar  # lazy: module import must not require network/identity

        edgar.set_identity(self._identity)

        try:
            company = edgar.Company(ticker)
            facts = company.get_facts()
        except Exception as exc:
            raise UpstreamError(
                f"EDGAR lookup failed for {ticker!r}: {exc}",
                code=ErrorCode.FILINGS_UNAVAILABLE,
            ) from exc
        if facts is None:
            raise UpstreamError(
                f"EDGAR has no XBRL facts for {ticker!r}",
                code=ErrorCode.FILINGS_UNAVAILABLE,
            )

        def series_for(keys: list[str]) -> pd.Series[float]:
            """First concept that resolves wins (normalization fallback)."""
            for k in keys:
                try:
                    s = _annual_series(facts, k)
                    if len(s):
                        return s.tail(years)
                except Exception:
                    log.debug("edgar.concept_failed", ticker=ticker, concept=k)
                    continue
            return pd.Series(dtype=float)

        rev = series_for(CONCEPTS["revenue"])
        ebit = series_for(CONCEPTS["ebit"])
        da = series_for(CONCEPTS["da"])
        capex = series_for(CONCEPTS["capex"]).abs()
        pretax = series_for(CONCEPTS["pretax"])
        tax = series_for(CONCEPTS["tax"])
        tax_rate = (tax / pretax).clip(0, 0.5) if len(pretax) else pd.Series(dtype=float)

        # Audit trail: one SourceLink per 10-K consumed (prime directive #4).
        sources: list[SourceLink] = []
        try:
            for f in company.get_filings(form="10-K").head(years):
                sources.append(
                    SourceLink(
                        label=f"10-K {f.filing_date}",
                        url=str(getattr(f, "homepage_url", "") or getattr(f, "url", "") or ""),
                        accession=str(getattr(f, "accession_no", "")),
                    )
                )
        except Exception:
            log.warning("edgar.source_links_failed", ticker=ticker)

        log.info(
            "edgar.fetched",
            ticker=ticker,
            revenue_years=len(rev),
            sources=len(sources),
        )
        return CompanyFinancials(
            ticker=ticker.upper(),
            name=str(getattr(company, "name", ticker)),
            sector=str(getattr(company, "sector", None) or "Unknown"),
            industry=str(getattr(company, "industry", None) or "Unknown"),
            sic=str(getattr(company, "sic", "") or ""),
            revenue=rev,
            ebit=ebit,
            da=da,
            capex=capex,
            tax_rate=tax_rate,
            sources=sources,
        )
        # Capital-structure fields (debt/cash/shares/price/beta) come from a
        # MarketDataProvider via CompanyFinancials.apply_market_snapshot().


def _annual_series(facts: Any, concept: str) -> pd.Series[float]:
    """Annual (12-month, FY) series for one concept, in $M, indexed by the
    fiscal year of `period_end`, restatements deduped to the latest filing."""
    df = (
        facts.query().by_concept(concept).by_fiscal_period("FY").by_period_length(12).to_dataframe()
    )
    if df is None or len(df) == 0 or "numeric_value" not in df.columns:
        return pd.Series(dtype=float)
    # edgartools' by_concept matches fuzzily (live finding: querying
    # IncomeTaxExpenseBenefit also returns DeferredIncomeTaxExpenseBenefit
    # rows from the cash-flow statement). Keep exact-concept rows only.
    if "concept" in df.columns:
        df = df[df["concept"].isin([concept, f"us-gaap:{concept}"])]
    d = df.dropna(subset=["numeric_value", "period_end"])
    if len(d) == 0:
        return pd.Series(dtype=float)
    # keep the most recently filed value per fiscal period, oldest -> newest
    d = d.sort_values("filing_date").groupby("period_end", as_index=False).last()
    d = d.sort_values("period_end")
    years = [int(str(pe)[:4]) for pe in d["period_end"]]
    values = [float(v) / _MM for v in d["numeric_value"]]
    return pd.Series(values, index=pd.Index(years, name="fiscal_year"), dtype=float)
