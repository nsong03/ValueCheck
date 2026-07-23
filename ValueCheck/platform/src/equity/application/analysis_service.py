"""Analysis service: the balcony (Phase 9c) — experimental models/studies
with EXPLICIT links to companies, references, and other analyses.

These links are distinct from tag-based association: a shared tag between
a note and an analysis is incidental ("both happen to mention value
investing"), but "AAPL is a constituent of this correlation study" is a
structural fact the analysis carries deliberately — that's what
`add_company`/`add_reference`/`add_link` record.
"""

from __future__ import annotations

from equity.domain.analysis import Analysis
from equity.errors import NotFoundError, ValidationError
from equity.logging import get_logger
from equity.ports.repository import AnalysisRepo

log = get_logger(__name__)


class AnalysisService:
    def __init__(self, analyses: AnalysisRepo) -> None:
        self._analyses = analyses

    # -- CRUD -------------------------------------------------------------------
    def create(self, *, kind: str, title: str, summary: str = "") -> Analysis:
        kind = kind.strip()
        title = title.strip()
        if not kind or not title:
            raise ValidationError("analysis requires kind and title")
        stored = self._analyses.save(Analysis(kind=kind, title=title, summary=summary))
        log.info("analysis.created", analysis_id=stored.id, kind=kind)
        return stored

    def get(self, analysis_id: int) -> Analysis:
        analysis = self._analyses.get(analysis_id)
        if analysis is None:
            raise NotFoundError(f"analysis {analysis_id} not found")
        return analysis

    def list_all(self) -> list[Analysis]:
        return self._analyses.list_all()

    def update(
        self,
        analysis_id: int,
        *,
        kind: str | None = None,
        title: str | None = None,
        summary: str | None = None,
    ) -> Analysis:
        existing = self.get(analysis_id)
        existing.kind = kind.strip() if kind is not None else existing.kind
        existing.title = title.strip() if title is not None else existing.title
        existing.summary = summary if summary is not None else existing.summary
        stored = self._analyses.save(existing)
        log.info("analysis.updated", analysis_id=analysis_id)
        return stored

    def delete(self, analysis_id: int) -> None:
        if not self._analyses.delete(analysis_id):
            raise NotFoundError(f"analysis {analysis_id} not found")
        log.info("analysis.deleted", analysis_id=analysis_id)

    # -- company constituents -----------------------------------------------
    def add_company(self, analysis_id: int, ticker: str) -> None:
        self.get(analysis_id)  # 404 before silently no-op'ing on a bad id
        ticker = ticker.upper().strip()
        if not ticker:
            raise ValidationError("ticker must be non-empty")
        self._analyses.add_company(analysis_id, ticker)
        log.info("analysis.company_added", analysis_id=analysis_id, ticker=ticker)

    def remove_company(self, analysis_id: int, ticker: str) -> None:
        self._analyses.remove_company(analysis_id, ticker.upper().strip())

    def companies(self, analysis_id: int) -> list[str]:
        return self._analyses.list_companies(analysis_id)

    def analyses_for_company(self, ticker: str) -> list[Analysis]:
        """Every analysis that explicitly includes this ticker — the
        "what models have I built that touch this stock?" lookup."""
        return self._analyses.list_for_company(ticker.upper().strip())

    # -- reference constituents ------------------------------------------------
    def add_reference(self, analysis_id: int, reference_id: int) -> None:
        self.get(analysis_id)
        self._analyses.add_reference(analysis_id, reference_id)
        log.info("analysis.reference_added", analysis_id=analysis_id, reference_id=reference_id)

    def remove_reference(self, analysis_id: int, reference_id: int) -> None:
        self._analyses.remove_reference(analysis_id, reference_id)

    def references(self, analysis_id: int) -> list[int]:
        return self._analyses.list_references(analysis_id)

    def analyses_for_reference(self, reference_id: int) -> list[Analysis]:
        """Every analysis that explicitly cites this reference."""
        return self._analyses.list_for_reference(reference_id)

    # -- analysis <-> analysis links -------------------------------------------
    def add_link(self, analysis_id: int, linked_analysis_id: int) -> None:
        if analysis_id == linked_analysis_id:
            raise ValidationError("an analysis cannot link to itself")
        self.get(analysis_id)
        self.get(linked_analysis_id)
        self._analyses.add_link(analysis_id, linked_analysis_id)
        log.info(
            "analysis.link_added", analysis_id=analysis_id, linked_analysis_id=linked_analysis_id
        )

    def remove_link(self, analysis_id: int, linked_analysis_id: int) -> None:
        self._analyses.remove_link(analysis_id, linked_analysis_id)

    def links(self, analysis_id: int) -> list[int]:
        """Ids of analyses this one explicitly links to (outgoing)."""
        return self._analyses.list_links(analysis_id)
