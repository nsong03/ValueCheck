"""Sensitivity grid tests: golden reproduction + structural properties."""

from __future__ import annotations

import pytest

from equity.domain.assumptions import Assumptions
from equity.domain.dcf import DCF
from equity.domain.models import CompanyFinancials

# seed/engine.py sensitivity() on the fully-seeded demo company (already
# rounded to 2dp by the engine itself)
GOLDEN_GRID = [
    [119.09, 127.75, 138.08, 150.64, 166.20],
    [101.77, 107.88, 114.97, 123.32, 133.28],
    [88.71, 93.20, 98.32, 104.20, 111.04],
    [78.49, 81.91, 85.74, 90.07, 95.01],
    [70.30, 72.96, 75.91, 79.21, 82.90],
]
GOLDEN_INDEX = ["WACC 7.7%", "WACC 8.7%", "WACC 9.7%", "WACC 10.7%", "WACC 11.7%"]
GOLDEN_COLUMNS = ["g 1.50%", "g 2.00%", "g 2.50%", "g 3.00%", "g 3.50%"]


@pytest.fixture
def dcf(demo_fin: CompanyFinancials) -> DCF:
    return DCF(demo_fin, Assumptions.seed_from(demo_fin, horizon=5))


class TestGoldenGrid:
    def test_reproduces_seed_grid(self, dcf: DCF) -> None:
        sens = dcf.sensitivity()
        assert list(sens.index) == GOLDEN_INDEX
        assert list(sens.columns) == GOLDEN_COLUMNS
        for i, row in enumerate(GOLDEN_GRID):
            got = [float(x) for x in sens.iloc[i]]
            assert got == pytest.approx(row, abs=1e-9), f"row {i} diverged"


class TestGridProperties:
    def test_center_cell_is_base_case(self, dcf: DCF) -> None:
        sens = dcf.sensitivity()
        base = dcf.value().fair_value_per_share
        assert float(sens.iloc[2, 2]) == pytest.approx(base, abs=0.005)  # engine rounds to 2dp

    def test_value_decreases_as_wacc_rises(self, dcf: DCF) -> None:
        sens = dcf.sensitivity()
        for j in range(sens.shape[1]):
            col = [float(x) for x in sens.iloc[:, j]]
            assert col == sorted(col, reverse=True), f"column {j} not decreasing in WACC"

    def test_value_increases_with_terminal_growth(self, dcf: DCF) -> None:
        sens = dcf.sensitivity()
        for i in range(sens.shape[0]):
            row = [float(x) for x in sens.iloc[i, :]]
            assert row == sorted(row), f"row {i} not increasing in g"

    def test_engine_state_untouched_after_sensitivity(self, dcf: DCF) -> None:
        before_beta = dcf.a.beta
        before_g = dcf.a.terminal_growth
        dcf.sensitivity()
        assert dcf.a.beta == before_beta
        assert dcf.a.terminal_growth == before_g

    def test_custom_grid_size(self, dcf: DCF) -> None:
        sens = dcf.sensitivity(n=3)
        assert sens.shape == (3, 3)
