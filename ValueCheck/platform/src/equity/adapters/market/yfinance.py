"""Yahoo Finance market-data adapter — the live MarketDataProvider.

Ported from the seed prototype (seed/market.py YFinanceProvider). Robust to
yfinance's habit of moving fields between `fast_info`, `info`, and the balance
sheet across versions: tries fast_info first (fast, stable), falls back to
`.info`, and pulls debt/cash from the balance sheet when the summary fields
are absent. Values are converted to $millions.

Verified live against yfinance 1.5.1 (Phase 2 smoke): fast_info exposes
`lastPrice`/`shares`, `.info` carries beta/totalDebt/totalCash, and the
balance-sheet fallback rows exist under the same labels the seed predicted.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from equity.domain.models import MarketSnapshot
from equity.errors import ErrorCode, UpstreamError
from equity.logging import get_logger

log = get_logger(__name__)

_QUOTE_URL = "https://finance.yahoo.com/quote/"


class YFinanceProvider:
    """Live market data via Yahoo Finance (free, unofficial)."""

    _MM = 1_000_000.0

    def snapshot(self, ticker: str) -> MarketSnapshot:
        import yfinance as yf  # lazy: module import must not require network

        try:
            t = yf.Ticker(ticker)
        except Exception as exc:
            raise UpstreamError(
                f"yfinance lookup failed for {ticker!r}: {exc}",
                code=ErrorCode.MARKET_DATA_UNAVAILABLE,
            ) from exc
        notes: list[str] = []

        # --- price & shares: prefer fast_info (cheap, reliable) ----------
        price: float | None = None
        shares: float | None = None
        beta: float | None = None
        total_debt: float | None = None
        cash: float | None = None
        try:
            fi = t.fast_info
            price = _get(fi, "last_price", "lastPrice")
            shares = _get(fi, "shares", "sharesOutstanding")
        except Exception:
            pass

        info: dict[str, Any] = {}
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
                        cash = _row(
                            col,
                            "Cash And Cash Equivalents",
                            "Cash Cash Equivalents And Short Term Investments",
                        )
            except Exception:
                pass

        if beta is None:
            beta = 1.0
            notes.append("beta missing -> defaulted to 1.0")

        snap = MarketSnapshot(
            price=_f(price),
            shares_out=_f(shares) / self._MM if shares else 0.0,
            total_debt=_f(total_debt) / self._MM if total_debt else 0.0,
            cash=_f(cash) / self._MM if cash else 0.0,
            beta=_f(beta, 1.0),
            currency=str(info.get("currency", "USD")),
            as_of=_dt.date.today().isoformat(),
            provider="yfinance",
            source_url=_QUOTE_URL + ticker,
            note="; ".join(notes),
        )
        log.info("yfinance.snapshot", ticker=ticker, complete=snap.is_complete(), note=snap.note)
        return snap


# --------------------------------------------------------------------------- #
# small helpers (from the seed core)
# --------------------------------------------------------------------------- #
def _get(obj: Any, *names: str) -> Any:
    for n in names:
        try:
            v = obj.get(n) if hasattr(obj, "get") else getattr(obj, n, None)
            if v is not None:
                return v
        except Exception:
            continue
    return None


def _row(col: Any, *labels: str) -> Any:
    for lab in labels:
        try:
            if lab in col.index:
                return col.loc[lab]
        except Exception:
            continue
    return None


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default
