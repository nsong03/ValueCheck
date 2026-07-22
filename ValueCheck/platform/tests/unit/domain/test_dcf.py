"""Behavior-parity tests: the ported engine must reproduce the seed engine.

GOLDEN numbers were produced by actually running the validated prototype
(seed/engine.py + seed/data.py SyntheticSource, horizon=5) on this machine
on 2026-07-21 (Python 3.12.13, pandas 3.0.3, numpy 2.5.1). Acceptance
criterion (BUILD_SPEC Phase 1): a known-input DCF reproduces the seed code's
numbers within floating tolerance.
"""

from __future__ import annotations

import pytest

from equity.domain.assumptions import Assumptions
from equity.domain.dcf import DCF
from equity.domain.models import CompanyFinancials

REL = 1e-12  # ported math should be float-identical; allow only representation noise

# seed/engine.py output, fully-seeded assumptions (case A)
GOLDEN_A = {
    "wacc": 0.09669424999999998,
    "enterprise_value": 1578350.5831670281,
    "equity_value": 1528817.5831670281,
    "fair_value_per_share": 98.31624329048412,
    "upside": -0.49581413697187626,
}

GOLDEN_A_PROJECTION = {
    "revenue": [
        422265.08449999994,
        457640.34195398743,
        487775.9584716575,
        511152.6212814117,
        526487.199919854,
    ],
    "growth": [0.1017, 0.083775, 0.06584999999999999, 0.047924999999999995, 0.03],
    "ebit": [
        117051.88142339999,
        126857.90278964532,
        135211.49568834345,
        141691.50661920733,
        145942.25181778354,
    ],
    "nopat": [
        99611.15109131338,
        107956.07527398816,
        115064.98283078027,
        120579.47213294543,
        124196.8562969338,
    ],
    "da": [
        14990.410499749996,
        16246.232139366552,
        17316.046525743837,
        18145.918055490114,
        18690.295597154818,
    ],
    "capex": [
        12921.311585699998,
        14003.794463792015,
        14925.944329232718,
        15641.270211211197,
        16110.508317547534,
    ],
    "d_nwc": [
        389.8008449999994,
        353.7525745398749,
        301.3561651767005,
        233.766628097542,
        153.34578638442386,
    ],
    "fcff": [
        101290.44916036338,
        109844.76037502282,
        117153.7288621147,
        122850.35334912682,
        126623.29779015665,
    ],
    "discount": [
        1.09669425,
        1.2027382779830627,
        1.3190361537189266,
        1.4465793653256631,
        1.586455272121304,
    ],
    "pv_fcff": [
        92359.78866522129,
        91328.8970558312,
        88817.6783720509,
        84924.72400328341,
        79815.23337928353,
    ],
}

# seed/run.py manual-override case: ebit_margin=0.29, terminal_growth=0.025 (case B)
GOLDEN_B = {
    "wacc": 0.09669424999999998,
    "enterprise_value": 1649863.406057869,
    "equity_value": 1600330.406057869,
    "fair_value_per_share": 102.91513865323917,
    "upside": -0.47223005818851704,
}


class TestGoldenCaseA:
    """Fully-seeded assumptions: DCF(fin) with Assumptions.seed_from defaults."""

    @pytest.fixture
    def dcf(self, demo_fin: CompanyFinancials) -> DCF:
        return DCF(demo_fin, Assumptions.seed_from(demo_fin, horizon=5))

    def test_wacc(self, dcf: DCF) -> None:
        assert dcf.wacc() == pytest.approx(GOLDEN_A["wacc"], rel=REL)

    def test_headline_numbers(self, dcf: DCF) -> None:
        res = dcf.value()
        assert res.enterprise_value == pytest.approx(GOLDEN_A["enterprise_value"], rel=REL)
        assert res.equity_value == pytest.approx(GOLDEN_A["equity_value"], rel=REL)
        assert res.fair_value_per_share == pytest.approx(GOLDEN_A["fair_value_per_share"], rel=REL)
        assert res.upside == pytest.approx(GOLDEN_A["upside"], rel=REL)
        assert res.warnings == []

    def test_full_projection(self, dcf: DCF) -> None:
        proj = dcf.project()
        assert list(proj.index) == [1, 2, 3, 4, 5]
        for col, expected in GOLDEN_A_PROJECTION.items():
            got = [float(x) for x in proj[col]]
            assert got == pytest.approx(expected, rel=REL), f"column {col!r} diverged"

    def test_default_assumptions_are_seeded(self, demo_fin: CompanyFinancials) -> None:
        # DCF(fin) with no assumptions must seed from history (seed behavior)
        implicit = DCF(demo_fin).value()
        explicit = DCF(demo_fin, Assumptions.seed_from(demo_fin)).value()
        assert implicit.fair_value_per_share == pytest.approx(
            explicit.fair_value_per_share, rel=REL
        )


class TestGoldenCaseB:
    """Manual overrides on top of seeding — mirrors seed/run.py."""

    def test_headline_numbers(self, demo_fin: CompanyFinancials) -> None:
        a = Assumptions.seed_from(demo_fin, horizon=5)
        a.ebit_margin = 0.29
        a.terminal_growth = 0.025
        res = DCF(demo_fin, a).value()
        assert res.wacc == pytest.approx(GOLDEN_B["wacc"], rel=REL)
        assert res.enterprise_value == pytest.approx(GOLDEN_B["enterprise_value"], rel=REL)
        assert res.equity_value == pytest.approx(GOLDEN_B["equity_value"], rel=REL)
        assert res.fair_value_per_share == pytest.approx(GOLDEN_B["fair_value_per_share"], rel=REL)
        assert res.upside == pytest.approx(GOLDEN_B["upside"], rel=REL)


class TestResultStructure:
    def test_result_carries_inputs_and_sources(self, demo_fin: CompanyFinancials) -> None:
        res = DCF(demo_fin).value()
        assert res.fin is demo_fin
        assert len(res.fin.sources) == 5  # audit trail intact
        assert res.assumptions.horizon == 5

    def test_missing_shares_gives_nan_per_share(self, demo_fin: CompanyFinancials) -> None:
        demo_fin.shares_out = 0.0
        res = DCF(demo_fin).value()
        assert res.fair_value_per_share != res.fair_value_per_share  # NaN

    def test_missing_price_gives_nan_upside(self, demo_fin: CompanyFinancials) -> None:
        demo_fin.price = 0.0
        res = DCF(demo_fin).value()
        assert res.upside != res.upside  # NaN
