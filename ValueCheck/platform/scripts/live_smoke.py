"""LIVE smoke test — hits real SEC EDGAR + Yahoo Finance. NEVER runs in CI.

The first (and canonical) exercise of the live data paths the prototype could
not reach. Fetches filings, enriches with market data, runs the DCF, and
prints everything a human needs to audit the run.

Usage:
    EQUITY_EDGAR_IDENTITY="Your Name you@example.com" \
        uv run python scripts/live_smoke.py [TICKER] [--years 5] [--horizon 5]
"""

from __future__ import annotations

import argparse
import dataclasses
import sys

import pandas as pd

from equity.adapters.filings.edgar import EdgarFilingsSource
from equity.adapters.market.yfinance import YFinanceProvider
from equity.config import get_settings
from equity.domain.assumptions import Assumptions
from equity.domain.dcf import DCF

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 20)


def money(x: float) -> str:
    return f"${x:,.0f}M" if abs(x) >= 1000 else f"${x:,.1f}M"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker", nargs="?", default="AAPL")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--horizon", type=int, default=5)
    args = parser.parse_args()

    settings = get_settings()
    if not settings.edgar_identity:
        print("ERROR: set EQUITY_EDGAR_IDENTITY (SEC fair-access requires it).")
        return 2

    print("=" * 72)
    print("  LIVE SMOKE — real network calls to SEC EDGAR + Yahoo Finance")
    print("=" * 72)

    print(f"\n[1/3] EDGAR: fetching {args.ticker} XBRL facts ({args.years}y) ...")
    fin = EdgarFilingsSource(settings.edgar_identity).fetch(args.ticker, years=args.years)

    print(f"[2/3] Yahoo: fetching market snapshot for {args.ticker} ...")
    snap = YFinanceProvider().snapshot(args.ticker)
    fin.apply_market_snapshot(snap)
    if snap.note:
        print(f"      note: {snap.note}")

    print("[3/3] Running DCF ...\n")
    print("=" * 72)
    print(f"  {fin.name}  ({fin.ticker})")
    print(f"  {fin.sector} / {fin.industry}   SIC {fin.sic}")
    print(
        f"  Price ${fin.price:.2f}  |  Shares {fin.shares_out:,.0f}M  |  "
        f"Mkt cap {money(fin.market_cap)}  |  Net debt {money(fin.net_debt)}"
    )
    print("=" * 72)

    print("\nHISTORICALS (from filings, $M)")
    print(fin.historicals_table().to_string())
    print(
        f"\n  Revenue CAGR: {fin.revenue_cagr():.1%}   Avg EBIT margin: {fin.avg_ebit_margin():.1%}"
    )

    a = Assumptions.seed_from(fin, horizon=args.horizon)
    dcf = DCF(fin, a)
    res = dcf.value()

    print("\nASSUMPTIONS (seeded from history — analyst overrides these)")
    for k, v in dataclasses.asdict(a).items():
        print(f"  {k:22s} {v:.4f}" if isinstance(v, float) else f"  {k:22s} {v}")

    print("\nPROJECTION (FCFF, $M)")
    print(res.projection.round(1).to_string())

    print("\nVALUATION")
    print(f"  WACC                {res.wacc:.2%}")
    print(f"  Enterprise value    {money(res.enterprise_value)}")
    print(f"  (-) Net debt        {money(fin.net_debt)}")
    print(f"  Equity value        {money(res.equity_value)}")
    print(f"  Fair value / share  ${res.fair_value_per_share:,.2f}")
    print(f"  Current price       ${fin.price:,.2f}")
    print(f"  Implied upside      {res.upside:+.1%}")

    if res.warnings:
        print("\n  ! WARNINGS")
        for w in res.warnings:
            print(f"    - {w}")

    print("\nSENSITIVITY — fair value / share (WACC x terminal growth)")
    print(dcf.sensitivity().to_string())

    print("\nSOURCES (click through to verify every input)")
    for s in fin.sources:
        print(f"  {s.label:34s} {s.url}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
