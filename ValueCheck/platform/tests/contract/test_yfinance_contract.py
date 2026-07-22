"""Contract tests for the yfinance adapter — mocked network, CI-safe.

A fake `yfinance` module is injected into sys.modules so the adapter's lazy
`import yfinance` binds to it. The fakes mirror the REAL yfinance 1.5.1
surface observed in the Phase 2 live probe (fast_info keys, info fields,
balance-sheet row labels).
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pandas as pd
import pytest

from equity.adapters.market.yfinance import YFinanceProvider

pytestmark = pytest.mark.contract


class FakeFastInfo(dict):  # type: ignore[type-arg]
    """fast_info behaves dict-like (`.get`) with camelCase keys."""


class FakeTicker:
    def __init__(
        self,
        fast_info: Any = None,
        info: Any = None,
        balance_sheet: pd.DataFrame | None = None,
    ) -> None:
        self._fast_info = fast_info
        self._info = info
        self._balance_sheet = balance_sheet

    @property
    def fast_info(self) -> Any:
        if isinstance(self._fast_info, Exception):
            raise self._fast_info
        return self._fast_info

    @property
    def info(self) -> Any:
        if isinstance(self._info, Exception):
            raise self._info
        return self._info

    @property
    def balance_sheet(self) -> pd.DataFrame | None:
        return self._balance_sheet


def install_fake_yfinance(monkeypatch: pytest.MonkeyPatch, ticker: FakeTicker) -> None:
    fake = types.ModuleType("yfinance")
    fake.Ticker = lambda symbol: ticker  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", fake)


class TestHappyPath:
    def test_fast_info_and_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        install_fake_yfinance(
            monkeypatch,
            FakeTicker(
                fast_info=FakeFastInfo(lastPrice=100.0, shares=2_000_000_000),
                info={
                    "beta": 1.5,
                    "totalDebt": 5_000_000_000,
                    "totalCash": 1_000_000_000,
                    "currency": "USD",
                },
            ),
        )
        snap = YFinanceProvider().snapshot("TEST")

        assert snap.price == 100.0
        assert snap.shares_out == 2000.0  # converted to millions
        assert snap.total_debt == 5000.0
        assert snap.cash == 1000.0
        assert snap.beta == 1.5
        assert snap.currency == "USD"
        assert snap.provider == "yfinance"
        assert snap.source_url.endswith("/quote/TEST")
        assert snap.is_complete()
        assert snap.note == ""


class TestFallbacks:
    def test_price_and_shares_from_info_when_fast_info_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_fake_yfinance(
            monkeypatch,
            FakeTicker(
                fast_info=RuntimeError("fast_info exploded"),
                info={
                    "currentPrice": 55.0,
                    "sharesOutstanding": 1_000_000_000,
                    "beta": 0.9,
                    "totalDebt": 2_000_000_000,
                    "totalCash": 500_000_000,
                },
            ),
        )
        snap = YFinanceProvider().snapshot("TEST")
        assert snap.price == 55.0
        assert snap.shares_out == 1000.0
        assert snap.beta == 0.9

    def test_debt_and_cash_from_balance_sheet(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bs = pd.DataFrame(
            {"2025-12-31": [3_000_000_000.0, 750_000_000.0]},
            index=["Total Debt", "Cash And Cash Equivalents"],
        )
        install_fake_yfinance(
            monkeypatch,
            FakeTicker(
                fast_info=FakeFastInfo(lastPrice=10.0, shares=100_000_000),
                info={"beta": 1.1},  # no debt/cash in summary
                balance_sheet=bs,
            ),
        )
        snap = YFinanceProvider().snapshot("TEST")
        assert snap.total_debt == 3000.0
        assert snap.cash == 750.0

    def test_missing_beta_defaults_with_note(self, monkeypatch: pytest.MonkeyPatch) -> None:
        install_fake_yfinance(
            monkeypatch,
            FakeTicker(
                fast_info=FakeFastInfo(lastPrice=10.0, shares=100_000_000),
                info={"totalDebt": 1_000_000, "totalCash": 1_000_000},
            ),
        )
        snap = YFinanceProvider().snapshot("TEST")
        assert snap.beta == 1.0
        assert "beta missing" in snap.note

    def test_info_unavailable_noted_and_degrades(self, monkeypatch: pytest.MonkeyPatch) -> None:
        install_fake_yfinance(
            monkeypatch,
            FakeTicker(
                fast_info=FakeFastInfo(lastPrice=10.0, shares=100_000_000),
                info=RuntimeError("rate limited"),
            ),
        )
        snap = YFinanceProvider().snapshot("TEST")
        assert snap.price == 10.0
        assert "info block unavailable" in snap.note
        assert snap.total_debt == 0.0  # degraded, not raised
        assert snap.beta == 1.0
