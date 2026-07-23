"""Screener DTOs: one row per company for a spreadsheet-style view."""

from __future__ import annotations

from pydantic import BaseModel

from equity.api.schemas.attributes import AttributeDefinitionOut, AttributeValueOut
from equity.api.schemas.company import none_if_nan
from equity.application.screener_service import ScreenerRow


class ScreenerValuationOut(BaseModel):
    id: int
    created_at: str
    fair_value_per_share: float | None
    upside: float | None
    wacc: float


class ScreenerRowOut(BaseModel):
    ticker: str
    name: str
    sector: str
    industry: str
    price: float
    market_cap: float
    net_debt: float
    beta: float
    revenue_cagr: float
    avg_ebit_margin: float
    latest_valuation: ScreenerValuationOut | None
    tags: list[str]
    note_count: int
    attributes: dict[str, AttributeValueOut]

    @classmethod
    def from_domain(cls, row: ScreenerRow) -> ScreenerRowOut:
        lv = row.latest_valuation
        return cls(
            ticker=row.ticker,
            name=row.name,
            sector=row.sector,
            industry=row.industry,
            price=row.price,
            market_cap=row.market_cap,
            net_debt=row.net_debt,
            beta=row.beta,
            revenue_cagr=row.revenue_cagr,
            avg_ebit_margin=row.avg_ebit_margin,
            latest_valuation=(
                ScreenerValuationOut(
                    id=lv.id,
                    created_at=lv.created_at.isoformat(),
                    fair_value_per_share=none_if_nan(lv.fair_value_per_share),
                    upside=none_if_nan(lv.upside),
                    wacc=lv.wacc,
                )
                if lv is not None
                else None
            ),
            tags=row.tags,
            note_count=row.note_count,
            attributes={k: AttributeValueOut.from_domain(v) for k, v in row.attributes.items()},
        )


class ScreenerOut(BaseModel):
    rows: list[ScreenerRowOut]


class ScreenerColumnsOut(BaseModel):
    columns: list[AttributeDefinitionOut]
