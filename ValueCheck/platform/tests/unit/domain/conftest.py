"""Domain test fixtures. Pure data — no network, no adapters.

`demo_fin` replicates the seed prototype's SyntheticSource figures exactly
(seed/data.py), so domain results are directly comparable to the validated
seed engine's output (the golden numbers in test_dcf.py).
"""

from __future__ import annotations

import pandas as pd
import pytest

from equity.domain.models import CompanyFinancials, SourceLink


def make_demo_financials(years: int = 5) -> CompanyFinancials:
    """The seed SyntheticSource company: a large-cap hardware maker, verbatim."""
    yrs = list(range(2019, 2019 + years))
    idx = pd.Index(yrs, name="fiscal_year")
    return CompanyFinancials(
        ticker="DEMO",
        name="Demo Hardware Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        sic="3571",
        revenue=pd.Series([260174, 274515, 365817, 394328, 383285][:years], index=idx, dtype=float),
        ebit=pd.Series([63930, 66288, 108949, 119437, 114301][:years], index=idx, dtype=float),
        da=pd.Series([12547, 11056, 11284, 11104, 11519][:years], index=idx, dtype=float),
        capex=pd.Series([10495, 7309, 11085, 10708, 10959][:years], index=idx, dtype=float),
        nwc=pd.Series([-2500, -3100, -6200, -7400, -1900][:years], index=idx, dtype=float),
        tax_rate=pd.Series([0.159, 0.144, 0.133, 0.162, 0.147][:years], index=idx, dtype=float),
        total_debt=111088,
        cash=61555,
        shares_out=15550,
        price=195.0,
        beta=1.28,
        sources=[
            SourceLink(
                label=f"10-K FY{y}",
                url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=10-K&FY={y}",
                accession=f"0000320193-{y}-DEMO",
            )
            for y in yrs
        ],
    )


@pytest.fixture
def demo_fin() -> CompanyFinancials:
    return make_demo_financials()
