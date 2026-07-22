"""Valuation use-case: load -> DCF -> save -> return result + sources.

Orchestration only: financials come from the IngestionService (cache-first),
the math is the pure domain DCF, persistence goes through the ValuationRepo
port. The result carries the company's full SourceLink audit trail.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from equity.application.ingestion_service import IngestionService
from equity.domain.assumptions import Assumptions
from equity.domain.dcf import DCF
from equity.domain.valuation import DCFResult, ValuationRecord
from equity.logging import get_logger
from equity.ports.repository import ValuationRepo

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ValuationOutcome:
    """Everything one valuation run produces, for the API layer to shape."""

    result: DCFResult  # includes fin (with sources) + warnings
    record: ValuationRecord  # the persisted run (id + timestamp)
    sensitivity: pd.DataFrame  # fair value/share over WACC x terminal growth


class ValuationService:
    def __init__(self, ingestion: IngestionService, valuations: ValuationRepo) -> None:
        self._ingestion = ingestion
        self._valuations = valuations

    def value(
        self,
        ticker: str,
        assumptions: Assumptions | None = None,
        *,
        overrides: Mapping[str, float | int] | None = None,
        refresh: bool = False,
    ) -> ValuationOutcome:
        """Run one DCF for `ticker`.

        Assumptions resolve in this order: an explicit `assumptions` object
        wins; else seed from the company's history and apply any partial
        `overrides` (the API's edit-one-lever-and-revalue flow); else pure
        seeded defaults. Override keys must be Assumptions field names —
        the API schema guarantees this before they reach here.
        """
        fin = self._ingestion.get_company(ticker, refresh=refresh)
        if assumptions is None and overrides:
            assumptions = Assumptions.seed_from(fin)
            for key, val in overrides.items():  # keys pre-validated by the API schema
                setattr(assumptions, key, val)
        dcf = DCF(fin, assumptions)  # None -> Assumptions.seed_from(fin)
        result = dcf.value()
        record = self._valuations.save(result)
        log.info(
            "valuation.completed",
            ticker=fin.ticker,
            valuation_id=record.id,
            fair_value_per_share=result.fair_value_per_share,
            warnings=len(result.warnings),
        )
        return ValuationOutcome(
            result=result,
            record=record,
            sensitivity=dcf.sensitivity(),
        )

    def history(self, ticker: str) -> list[ValuationRecord]:
        """Stored runs for a ticker, newest first."""
        return self._valuations.list_for(ticker.upper().strip())

    def get(self, valuation_id: int) -> ValuationRecord | None:
        return self._valuations.get(valuation_id)
