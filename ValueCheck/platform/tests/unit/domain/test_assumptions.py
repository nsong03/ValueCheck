"""Unit tests for domain.assumptions — seed_from derivation incl. quirks."""

from __future__ import annotations

import pandas as pd
import pytest

from equity.domain.assumptions import Assumptions
from equity.domain.models import CompanyFinancials


class TestSeedFromGolden:
    """seed_from on the demo company must reproduce the seed engine's values."""

    def test_seeded_values_match_seed_engine(self, demo_fin: CompanyFinancials) -> None:
        a = Assumptions.seed_from(demo_fin, horizon=5)
        # golden: seed/engine.py Assumptions.seed_from on the same figures
        assert a.horizon == 5
        assert a.rev_growth == pytest.approx(0.1017)
        assert a.rev_growth_terminal == 0.03
        assert a.ebit_margin == pytest.approx(0.2772)
        assert a.tax_rate == pytest.approx(0.149)
        assert a.da_pct_rev == pytest.approx(0.0355)
        assert a.capex_pct_rev == pytest.approx(0.0306)
        assert a.beta == pytest.approx(1.28)
        # untouched levers keep class defaults
        assert a.nwc_pct_rev == 0.01
        assert a.risk_free == 0.043
        assert a.equity_premium == 0.05
        assert a.cost_of_debt == 0.045
        assert a.target_debt_weight == 0.15
        assert a.terminal_growth == 0.025


def _fin_with_revenue(revenues: list[float]) -> CompanyFinancials:
    idx = pd.Index(range(2019, 2019 + len(revenues)), name="fiscal_year")
    return CompanyFinancials(
        ticker="X",
        name="X",
        sector="?",
        industry="?",
        revenue=pd.Series(revenues, index=idx, dtype=float),
    )


class TestSeedFromClamps:
    def test_growth_clamped_to_15_percent(self) -> None:
        fin = _fin_with_revenue([100.0, 200.0, 400.0])  # 100% CAGR
        assert Assumptions.seed_from(fin).rev_growth == 0.15

    def test_negative_growth_clamped_to_zero(self) -> None:
        fin = _fin_with_revenue([400.0, 200.0, 100.0])
        assert Assumptions.seed_from(fin).rev_growth == 0.0


class TestSeedFromFallbacks:
    """Missing history falls back to explicit defaults (seed behavior)."""

    def test_empty_history_uses_defaults(self) -> None:
        fin = CompanyFinancials(ticker="X", name="X", sector="?", industry="?")
        a = Assumptions.seed_from(fin)
        assert a.rev_growth == 0.0
        assert a.ebit_margin == 0.20  # `or 0.20` quirk: zero margin -> 20%
        assert a.tax_rate == 0.15
        assert a.da_pct_rev == 0.03
        assert a.capex_pct_rev == 0.03
        assert a.beta == 1.0

    def test_zero_beta_falls_back_to_one(self, demo_fin: CompanyFinancials) -> None:
        demo_fin.beta = 0.0
        assert Assumptions.seed_from(demo_fin).beta == 1.0

    def test_nonzero_beta_preserved(self, demo_fin: CompanyFinancials) -> None:
        demo_fin.beta = 0.85
        assert Assumptions.seed_from(demo_fin).beta == 0.85
