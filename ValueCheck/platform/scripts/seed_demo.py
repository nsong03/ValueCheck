"""Seed the local database with the demo company (no network, no identity).

The figures are the validated seed prototype's SyntheticSource (seed/data.py):
a large-cap hardware maker whose numbers back the golden tests. Lets the UI
be exercised offline against ticker DEMO.

Usage: uv run python scripts/seed_demo.py [--db equity.db]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from equity.application.container import build_container
from equity.config import Settings
from equity.domain.models import CompanyFinancials, SourceLink


def demo_company() -> CompanyFinancials:
    years = list(range(2019, 2024))
    idx = pd.Index(years, name="fiscal_year")
    return CompanyFinancials(
        ticker="DEMO",
        name="Demo Hardware Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        sic="3571",
        revenue=pd.Series([260174, 274515, 365817, 394328, 383285], index=idx, dtype=float),
        ebit=pd.Series([63930, 66288, 108949, 119437, 114301], index=idx, dtype=float),
        da=pd.Series([12547, 11056, 11284, 11104, 11519], index=idx, dtype=float),
        capex=pd.Series([10495, 7309, 11085, 10708, 10959], index=idx, dtype=float),
        nwc=pd.Series([-2500, -3100, -6200, -7400, -1900], index=idx, dtype=float),
        tax_rate=pd.Series([0.159, 0.144, 0.133, 0.162, 0.147], index=idx, dtype=float),
        total_debt=111088,
        cash=61555,
        shares_out=15550,
        price=195.0,
        beta=1.28,
        sources=[
            SourceLink(
                label=f"10-K FY{y} (synthetic demo)",
                url="about:demo-data",
                accession=f"demo-{y}",
            )
            for y in years
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None, help="Database path override.")
    args = parser.parse_args()

    settings = Settings(database_path=args.db) if args.db else Settings()
    container = build_container(settings)
    container.companies.save(demo_company())
    print(f"seeded DEMO into {settings.database_path}")
    print("try:  curl -X POST http://127.0.0.1:8000/companies/DEMO/valuation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
