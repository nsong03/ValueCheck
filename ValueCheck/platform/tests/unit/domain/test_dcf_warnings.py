"""Warning triggers (BUILD_SPEC §5): both MUST fire on their conditions."""

from __future__ import annotations

from equity.domain.assumptions import Assumptions
from equity.domain.dcf import DCF
from equity.domain.models import CompanyFinancials


class TestTerminalGrowthWarning:
    def test_fires_when_terminal_growth_at_wacc(self, demo_fin: CompanyFinancials) -> None:
        a = Assumptions.seed_from(demo_fin)
        w = DCF(demo_fin, a).wacc()
        a.terminal_growth = w  # g == WACC -> perpetuity undefined
        res = DCF(demo_fin, a).value()
        assert any("terminal value is invalid" in msg for msg in res.warnings)
        # with g >= WACC the terminal value (and thus EV) is NaN, not a number
        assert res.enterprise_value != res.enterprise_value

    def test_fires_when_terminal_growth_above_wacc(self, demo_fin: CompanyFinancials) -> None:
        a = Assumptions.seed_from(demo_fin)
        a.terminal_growth = 0.20
        res = DCF(demo_fin, a).value()
        assert any("terminal value is invalid" in msg for msg in res.warnings)

    def test_silent_when_terminal_growth_below_wacc(self, demo_fin: CompanyFinancials) -> None:
        res = DCF(demo_fin, Assumptions.seed_from(demo_fin)).value()
        assert not any("terminal value is invalid" in msg for msg in res.warnings)


class TestTerminalValueShareWarning:
    def test_fires_when_tv_dominates_ev(self, demo_fin: CompanyFinancials) -> None:
        a = Assumptions.seed_from(demo_fin)
        # g just below WACC (~9.67%) -> tiny denominator -> TV dwarfs explicit years
        a.terminal_growth = 0.09
        res = DCF(demo_fin, a).value()
        assert any("sensitive to g and WACC" in msg for msg in res.warnings)
        # and the invalid-terminal warning must NOT fire (g < WACC)
        assert not any("terminal value is invalid" in msg for msg in res.warnings)

    def test_silent_on_moderate_terminal_share(self, demo_fin: CompanyFinancials) -> None:
        res = DCF(demo_fin, Assumptions.seed_from(demo_fin)).value()
        assert res.warnings == []
