"""
run.py — End-to-end demo of the DCF core.

On your machine, flip USE_REAL = True (after `edgar.set_identity(...)`) to pull
live XBRL. Here it uses SyntheticSource so the full engine runs offline.
"""

import pandas as pd
from data import SyntheticSource, EdgarSource
from engine import DCF, Assumptions

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 20)

USE_REAL = False   # -> True on your machine, after edgar.set_identity(...)
TICKER = "AAPL"


def money(x):
    return f"${x:,.0f}M" if abs(x) >= 1000 else f"${x:,.1f}M"


def main():
    src = EdgarSource() if USE_REAL else SyntheticSource()
    fin = src.fetch(TICKER, years=5)

    print("=" * 72)
    print(f"  {fin.name}  ({fin.ticker})")
    print(f"  {fin.sector} / {fin.industry}   SIC {fin.sic}")
    print(f"  Price ${fin.price:.2f}  |  Shares {fin.shares_out:,.0f}M  |  "
          f"Mkt cap {money(fin.market_cap)}  |  Net debt {money(fin.net_debt)}")
    print("=" * 72)

    print("\nHISTORICALS (from filings)")
    print(fin.historicals_table().to_string())
    print(f"\n  Revenue CAGR: {fin.revenue_cagr():.1%}   "
          f"Avg EBIT margin: {fin.avg_ebit_margin():.1%}")

    # Seed assumptions from history, then you'd tune these.
    a = Assumptions.seed_from(fin, horizon=5)
    a.ebit_margin = 0.29          # example manual override
    a.terminal_growth = 0.025
    dcf = DCF(fin, a)
    res = dcf.value()

    print("\nASSUMPTIONS (editable — this is where your judgment lives)")
    for k, v in a.__dict__.items():
        print(f"  {k:22s} {v:.4f}" if isinstance(v, float) else f"  {k:22s} {v}")

    print("\nPROJECTION (FCFF, $M)")
    show = res.projection[["revenue", "growth", "ebit", "nopat", "da",
                           "capex", "d_nwc", "fcff", "pv_fcff"]].copy()
    for c in ["revenue", "ebit", "nopat", "da", "capex", "d_nwc", "fcff", "pv_fcff"]:
        show[c] = show[c].map(lambda x: f"{x:,.0f}")
    show["growth"] = show["growth"].map(lambda x: f"{x:.1%}")
    print(show.to_string())

    print("\nVALUATION")
    print(f"  WACC                {res.wacc:.2%}")
    print(f"  Enterprise value    {money(res.enterprise_value)}")
    print(f"  (-) Net debt        {money(fin.net_debt)}")
    print(f"  Equity value        {money(res.equity_value)}")
    print(f"  Fair value / share  ${res.fair_value_per_share:,.2f}")
    print(f"  Current price       ${fin.price:,.2f}")
    print(f"  Implied upside      {res.upside:+.1%}")

    if res.warnings:
        print("\n  ⚠ WARNINGS")
        for wmsg in res.warnings:
            print(f"    - {wmsg}")

    print("\nSENSITIVITY — fair value / share  (WACC x terminal growth)")
    print(dcf.sensitivity().to_string())

    print("\nSOURCES (click through to verify every input)")
    for s in fin.sources:
        print(f"  {s.label:16s} {s.url}")


if __name__ == "__main__":
    main()
