"""Screener use-case: one row per company for a spreadsheet-style view,
joining financials, the latest valuation, tags, and current research
attributes (Phase 9). Orchestration only — no business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from equity.domain.attributes import AttributeDefinition, AttributeValue
from equity.domain.valuation import ValuationRecord
from equity.logging import get_logger
from equity.ports.repository import AttributeRepo, CompanyRepo, NoteRepo, ValuationRepo

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ScreenerRow:
    """Everything one grid row needs, shaped by the API layer into a DTO."""

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
    latest_valuation: ValuationRecord | None
    tags: list[str] = field(default_factory=list)
    note_count: int = 0
    attributes: dict[str, AttributeValue] = field(default_factory=dict)


class ScreenerService:
    def __init__(
        self,
        companies: CompanyRepo,
        valuations: ValuationRepo,
        notes: NoteRepo,
        attributes: AttributeRepo,
    ) -> None:
        self._companies = companies
        self._valuations = valuations
        self._notes = notes
        self._attributes = attributes

    def build_rows(self) -> list[ScreenerRow]:
        """One row per tracked company, sorted by ticker."""
        rows: list[ScreenerRow] = []
        for ticker in self._companies.list_tickers():
            fin = self._companies.get(ticker)
            if fin is None:  # deleted between list and get; skip
                continue
            history = self._valuations.list_for(ticker)
            notes = self._notes.list_for(ticker)
            tag_set: dict[str, None] = {}
            for note in notes:
                for tag in note.tags:
                    tag_set.setdefault(tag, None)
            rows.append(
                ScreenerRow(
                    ticker=fin.ticker,
                    name=fin.name,
                    sector=fin.sector,
                    industry=fin.industry,
                    price=fin.price,
                    market_cap=fin.market_cap,
                    net_debt=fin.net_debt,
                    beta=fin.beta,
                    revenue_cagr=fin.revenue_cagr(),
                    avg_ebit_margin=fin.avg_ebit_margin(),
                    latest_valuation=history[0] if history else None,
                    tags=sorted(tag_set),
                    note_count=len(notes),
                    attributes=self._attributes.current_for(ticker),
                )
            )
        log.info("screener.built", rows=len(rows))
        return rows

    def columns(self) -> list[AttributeDefinition]:
        """Every discovered attribute key, for the frontend to build columns
        dynamically instead of hardcoding custom dimensions."""
        return self._attributes.list_definitions()
