"""Valuation DTOs: request (partial assumptions) and responses.

The response mirrors BUILD_SPEC §5 `DCFResult`: projection records, wacc,
enterprise/equity value, fair value per share, upside, warnings — plus the
sensitivity grid and the source audit trail the endpoint contract requires.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

import pandas as pd
from pydantic import BaseModel, Field

from equity.api.schemas.company import SourceLinkOut, none_if_nan
from equity.application.valuation_service import ValuationOutcome
from equity.domain.assumptions import Assumptions
from equity.domain.valuation import ValuationRecord


class AssumptionsIn(BaseModel):
    """Partial assumption overrides. Anything omitted seeds from history.

    Bounds are sanity limits on the API contract; the domain itself stays
    permissive (it warns rather than rejects, e.g. terminal growth >= WACC).
    """

    horizon: int | None = Field(None, ge=1, le=30)
    rev_growth: float | None = Field(None, ge=-0.5, le=0.5)
    rev_growth_terminal: float | None = Field(None, ge=-0.5, le=0.5)
    ebit_margin: float | None = Field(None, ge=-1.0, le=1.0)
    tax_rate: float | None = Field(None, ge=0.0, le=1.0)
    da_pct_rev: float | None = Field(None, ge=0.0, le=1.0)
    capex_pct_rev: float | None = Field(None, ge=0.0, le=1.0)
    nwc_pct_rev: float | None = Field(None, ge=-1.0, le=1.0)
    risk_free: float | None = Field(None, ge=0.0, le=0.5)
    equity_premium: float | None = Field(None, ge=0.0, le=0.5)
    beta: float | None = Field(None, ge=-2.0, le=5.0)
    cost_of_debt: float | None = Field(None, ge=0.0, le=0.5)
    target_debt_weight: float | None = Field(None, ge=0.0, le=0.95)
    terminal_growth: float | None = Field(None, ge=-0.1, le=0.2)

    def overrides(self) -> dict[str, float | int]:
        """Only the fields the client actually set."""
        set_fields: dict[str, float | int] = self.model_dump(exclude_none=True)
        return set_fields


class AssumptionsOut(BaseModel):
    """The fully-resolved levers this valuation actually used."""

    horizon: int
    rev_growth: float
    rev_growth_terminal: float
    ebit_margin: float
    tax_rate: float
    da_pct_rev: float
    capex_pct_rev: float
    nwc_pct_rev: float
    risk_free: float
    equity_premium: float
    beta: float
    cost_of_debt: float
    target_debt_weight: float
    terminal_growth: float

    @classmethod
    def from_domain(cls, a: Assumptions) -> AssumptionsOut:
        return cls(**asdict(a))


class ProjectionRow(BaseModel):
    """One projected year of the FCFF build ($M)."""

    year: int
    revenue: float
    growth: float
    ebit: float
    nopat: float
    da: float
    capex: float
    d_nwc: float
    fcff: float
    discount: float
    pv_fcff: float


def projection_rows(df: pd.DataFrame) -> list[ProjectionRow]:
    return [
        ProjectionRow(year=int(str(idx)), **{c: float(row[c]) for c in df.columns})
        for idx, row in df.iterrows()
    ]


class SensitivityOut(BaseModel):
    """Fair value/share grid: rows = WACC levels, cols = terminal growth."""

    wacc_labels: list[str]
    growth_labels: list[str]
    grid: list[list[float | None]]

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> SensitivityOut:
        return cls(
            wacc_labels=[str(i) for i in df.index],
            growth_labels=[str(c) for c in df.columns],
            grid=[[none_if_nan(float(v)) for v in row] for _, row in df.iterrows()],
        )


class ValuationResponse(BaseModel):
    """POST /companies/{ticker}/valuation: result + sensitivity + sources."""

    valuation_id: int
    ticker: str
    created_at: datetime
    wacc: float
    enterprise_value: float | None
    equity_value: float | None
    fair_value_per_share: float | None
    upside: float | None
    warnings: list[str]
    assumptions: AssumptionsOut
    projection: list[ProjectionRow]
    sensitivity: SensitivityOut
    sources: list[SourceLinkOut]

    @classmethod
    def from_outcome(cls, outcome: ValuationOutcome) -> ValuationResponse:
        result = outcome.result
        return cls(
            valuation_id=outcome.record.id,
            ticker=result.fin.ticker,
            created_at=outcome.record.created_at,
            wacc=result.wacc,
            enterprise_value=none_if_nan(result.enterprise_value),
            equity_value=none_if_nan(result.equity_value),
            fair_value_per_share=none_if_nan(result.fair_value_per_share),
            upside=none_if_nan(result.upside),
            warnings=result.warnings,
            assumptions=AssumptionsOut.from_domain(result.assumptions),
            projection=projection_rows(result.projection),
            sensitivity=SensitivityOut.from_frame(outcome.sensitivity),
            sources=[SourceLinkOut.from_domain(s) for s in result.fin.sources],
        )


class ValuationRecordSummary(BaseModel):
    """One stored run, headline numbers only (history listings)."""

    id: int
    ticker: str
    created_at: datetime
    wacc: float
    enterprise_value: float | None
    equity_value: float | None
    fair_value_per_share: float | None
    upside: float | None
    warnings: list[str]

    @classmethod
    def from_record(cls, r: ValuationRecord) -> ValuationRecordSummary:
        return cls(
            id=r.id,
            ticker=r.ticker,
            created_at=r.created_at,
            wacc=r.wacc,
            enterprise_value=none_if_nan(r.enterprise_value),
            equity_value=none_if_nan(r.equity_value),
            fair_value_per_share=none_if_nan(r.fair_value_per_share),
            upside=none_if_nan(r.upside),
            warnings=r.warnings,
        )


class ValuationRecordDetail(ValuationRecordSummary):
    """A stored run in full: resolved assumptions + projection."""

    assumptions: AssumptionsOut
    projection: list[ProjectionRow]

    @classmethod
    def from_record(cls, r: ValuationRecord) -> ValuationRecordDetail:
        summary = ValuationRecordSummary.from_record(r)
        return cls(
            **summary.model_dump(),
            assumptions=AssumptionsOut.from_domain(r.assumptions),
            projection=projection_rows(r.projection),
        )
