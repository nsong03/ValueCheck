"""
market.py — Market-data adapter.

Fills the capital-structure fields that XBRL doesn't give you cleanly:
current price, shares outstanding, total debt, cash, and beta. These feed
WACC (beta) and the enterprise->equity bridge (net debt) and the per-share
result (price, shares).

Design: `MarketDataProvider` is the interface. `YFinanceProvider` is the
real implementation (runs on your machine). `MockProvider` returns fixed
values so the wiring is testable offline. The engine never imports this —
it only ever sees fields on a CompanyFinancials, so providers are swappable
(yfinance today, OpenBB / Alpha Vantage / a paid feed tomorrow).

Usage on your machine:
    from data import EdgarSource
    from market import YFinanceProvider, enrich
    fin = EdgarSource().fetch("AAPL")
    enrich(fin, YFinanceProvider())      # mutates fin in place, adds a source
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol
import datetime as _dt

from data import CompanyFinancials, SourceLink


# ---------------------------------------------------------------------------
# What every provider must return. All monetary values in millions USD to
# match CompanyFinancials; shares in millions.
# ---------------------------------------------------------------------------
@dataclass
class MarketSnapshot:
    price: float
    shares_out: float          # millions
    total_debt: float          # millions
    cash: float                # millions
    beta: float
    currency: str = "USD"
    as_of: str = ""            # ISO date
    provider: str = ""
    note: str = ""             # e.g. "beta defaulted to 1.0 (missing)"

    def is_complete(self) -> bool:
        return all(v is not None and v == v for v in
                   (self.price, self.shares_out, self.total_debt, self.cash, self.beta))


class MarketDataProvider(Protocol):
    def snapshot(self, ticker: str) -> MarketSnapshot: ...


# ---------------------------------------------------------------------------
# REAL provider — yfinance. Runs on your machine.
# ---------------------------------------------------------------------------
class YFinanceProvider:
    """Live market data via Yahoo Finance (free, unofficial).

    Robust to yfinance's habit of moving fields between `fast_info`, `info`,
    and the balance sheet across versions: it tries fast_info first (fast,
    stable), falls back to .info, and pulls debt/cash from the balance sheet
    when the summary fields are absent. Values are converted to $millions.
    """

    _MM = 1_000_000.0

    def snapshot(self, ticker: str) -> MarketSnapshot:
        import yfinance as yf
        t = yf.Ticker(ticker)
        notes = []

        # --- price & shares: prefer fast_info (cheap, reliable) ----------
        price = shares = beta = total_debt = cash = None
        try:
            fi = t.fast_info
            price = _get(fi, "last_price", "lastPrice")
            shares = _get(fi, "shares", "sharesOutstanding")
        except Exception:
            pass

        info = {}
        try:
            info = t.info or {}
        except Exception:
            notes.append("info block unavailable")

        if price is None:
            price = info.get("currentPrice") or info.get("regularMarketPrice")
        if shares is None:
            shares = info.get("sharesOutstanding")
        beta = info.get("beta")
        total_debt = info.get("totalDebt")
        cash = info.get("totalCash") or info.get("cash")

        # --- fall back to the balance sheet for debt / cash --------------
        if total_debt is None or cash is None:
            try:
                bs = t.balance_sheet  # DataFrame, most-recent column first
                if bs is not None and bs.shape[1] > 0:
                    col = bs.iloc[:, 0]
                    if total_debt is None:
                        total_debt = _row(col, "Total Debt")
                    if cash is None:
                        cash = _row(col, "Cash And Cash Equivalents",
                                    "Cash Cash Equivalents And Short Term Investments")
            except Exception:
                pass

        if beta is None:
            beta = 1.0
            notes.append("beta missing -> defaulted to 1.0")

        return MarketSnapshot(
            price=_f(price),
            shares_out=_f(shares) / self._MM if shares else 0.0,
            total_debt=_f(total_debt) / self._MM if total_debt else 0.0,
            cash=_f(cash) / self._MM if cash else 0.0,
            beta=_f(beta, 1.0),
            currency=info.get("currency", "USD"),
            as_of=_dt.date.today().isoformat(),
            provider="yfinance",
            note="; ".join(notes),
        )


# ---------------------------------------------------------------------------
# MOCK provider — fixed values so the wiring runs offline.
# ---------------------------------------------------------------------------
class MockProvider:
    def snapshot(self, ticker: str) -> MarketSnapshot:
        return MarketSnapshot(
            price=195.0, shares_out=15550.0, total_debt=111088.0, cash=61555.0,
            beta=1.28, currency="USD", as_of=_dt.date.today().isoformat(),
            provider="mock", note="synthetic values for offline demo",
        )


# ---------------------------------------------------------------------------
# The one function the app calls: enrich a CompanyFinancials in place.
# ---------------------------------------------------------------------------
def enrich(fin: CompanyFinancials, provider: MarketDataProvider,
           overwrite: bool = False) -> MarketSnapshot:
    """Populate fin's capital-structure fields from a market provider.

    Only fills fields that are unset (0.0) unless overwrite=True, so a value
    you've deliberately entered by hand is preserved. Appends a SourceLink so
    the market inputs are as auditable as the filing inputs.
    """
    snap = provider.snapshot(fin.ticker)

    def maybe(attr, val):
        if overwrite or not getattr(fin, attr):
            setattr(fin, attr, val)

    maybe("price", snap.price)
    maybe("shares_out", snap.shares_out)
    maybe("total_debt", snap.total_debt)
    maybe("cash", snap.cash)
    if overwrite or fin.beta in (0.0, 1.0, None):
        fin.beta = snap.beta

    fin.sources.append(SourceLink(
        label=f"Market data ({snap.provider}, {snap.as_of})",
        url="https://finance.yahoo.com/quote/" + fin.ticker,
        accession=snap.provider,
    ))
    return snap


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _get(obj, *names):
    for n in names:
        try:
            if hasattr(obj, "get"):
                v = obj.get(n)
            else:
                v = getattr(obj, n, None)
            if v is not None:
                return v
        except Exception:
            continue
    return None


def _row(col, *labels):
    for lab in labels:
        try:
            if lab in col.index:
                return col.loc[lab]
        except Exception:
            continue
    return None


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default
