"""Unit tests for domain.metrics — pure ratio helpers, incl. degenerate inputs."""

from __future__ import annotations

import pandas as pd
import pytest

from equity.domain import metrics


class TestCagr:
    def test_known_growth(self) -> None:
        s = pd.Series([100.0, 121.0], index=[2022, 2023])
        assert metrics.cagr(s) == pytest.approx(0.21)

    def test_multi_year(self) -> None:
        # 100 -> 200 over 4 steps: (2)^(1/4) - 1
        s = pd.Series([100.0, 120.0, 150.0, 170.0, 200.0], index=range(2019, 2024))
        assert metrics.cagr(s) == pytest.approx(2 ** (1 / 4) - 1)

    def test_single_point_returns_zero(self) -> None:
        assert metrics.cagr(pd.Series([100.0], index=[2023])) == 0.0

    def test_empty_returns_zero(self) -> None:
        assert metrics.cagr(pd.Series(dtype=float)) == 0.0

    def test_nonpositive_base_returns_zero(self) -> None:
        s = pd.Series([0.0, 50.0], index=[2022, 2023])
        assert metrics.cagr(s) == 0.0
        s_neg = pd.Series([-10.0, 50.0], index=[2022, 2023])
        assert metrics.cagr(s_neg) == 0.0

    def test_nans_dropped_before_computing(self) -> None:
        s = pd.Series([100.0, float("nan"), 121.0], index=[2021, 2022, 2023])
        # NaN dropped -> two observations remain -> one step: 121/100 - 1
        assert metrics.cagr(s) == pytest.approx(0.21, rel=1e-9)


class TestAverageRatio:
    def test_simple_mean(self) -> None:
        num = pd.Series([10.0, 30.0], index=[2022, 2023])
        den = pd.Series([100.0, 100.0], index=[2022, 2023])
        assert metrics.average_ratio(num, den) == pytest.approx(0.2)

    def test_misaligned_years_dropped(self) -> None:
        num = pd.Series([10.0], index=[2022])
        den = pd.Series([100.0, 100.0], index=[2022, 2023])
        assert metrics.average_ratio(num, den) == pytest.approx(0.1)

    def test_no_overlap_returns_zero(self) -> None:
        num = pd.Series([10.0], index=[2020])
        den = pd.Series([100.0], index=[2023])
        assert metrics.average_ratio(num, den) == 0.0

    def test_empty_returns_zero(self) -> None:
        empty = pd.Series(dtype=float)
        assert metrics.average_ratio(empty, empty) == 0.0


class TestMeanOr:
    def test_mean_of_values(self) -> None:
        s = pd.Series([0.1, 0.2, 0.3])
        assert metrics.mean_or(s, 0.99) == pytest.approx(0.2)

    def test_default_when_empty(self) -> None:
        assert metrics.mean_or(pd.Series(dtype=float), 0.15) == 0.15

    def test_nans_dropped(self) -> None:
        s = pd.Series([0.1, float("nan"), 0.3])
        assert metrics.mean_or(s, 0.99) == pytest.approx(0.2)
