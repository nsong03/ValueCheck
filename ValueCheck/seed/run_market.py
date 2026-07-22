"""
run_market.py — Demonstrates the market-data adapter composing with the core.

Simulates the real flow: XBRL gives income-statement history but NOT clean
price/shares/debt/cash/beta -> those come from the market provider. We build
a company with the capital-structure fields blank, enrich it, then value it.
"""

from data import SyntheticSource
from market import MockProvider, YFinanceProvider, enrich
from engine import DCF, Assumptions

USE_REAL = False  # -> True on your machine


def blank_capital_structure(fin):
    """Pretend XBRL gave us only the income statement."""
    fin.price = fin.shares_out = fin.total_debt = fin.cash = 0.0
    fin.beta = 1.0
    return fin


def main():
    fin = SyntheticSource().fetch("AAPL", years=5)
    blank_capital_structure(fin)

    print("BEFORE enrichment (as if straight from XBRL):")
    print(f"  price={fin.price}  shares={fin.shares_out}  "
          f"debt={fin.total_debt}  cash={fin.cash}  beta={fin.beta}")
    print(f"  net_debt={fin.net_debt}  market_cap={fin.market_cap}")

    provider = YFinanceProvider() if USE_REAL else MockProvider()
    snap = enrich(fin, provider)

    print(f"\nProvider: {snap.provider}  as_of={snap.as_of}")
    if snap.note:
        print(f"  note: {snap.note}")

    print("\nAFTER enrichment:")
    print(f"  price=${fin.price:.2f}  shares={fin.shares_out:,.0f}M  "
          f"debt=${fin.total_debt:,.0f}M  cash=${fin.cash:,.0f}M  beta={fin.beta}")
    print(f"  net_debt=${fin.net_debt:,.0f}M  market_cap=${fin.market_cap:,.0f}M")

    # Now the engine has everything it needs.
    a = Assumptions.seed_from(fin, horizon=5)
    a.ebit_margin = 0.29
    res = DCF(fin, a).value()
    print("\nVALUATION (capital-structure fields now sourced automatically):")
    print(f"  WACC {res.wacc:.2%}  |  EV ${res.enterprise_value:,.0f}M  |  "
          f"fair value ${res.fair_value_per_share:,.2f}  |  upside {res.upside:+.1%}")

    print("\nSOURCE TRAIL (filings + market data, all auditable):")
    for s in fin.sources:
        print(f"  {s.label:34s} {s.url}")


if __name__ == "__main__":
    main()
