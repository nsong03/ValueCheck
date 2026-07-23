"""The balcony: experimental analysis — financial models, portfolio
constructions, correlation studies — that explicitly link to the companies
and references they draw on (Phase 9c). Pure data, no I/O.

Unlike the company<->reference connection (which is only ever incidental,
through a shared tag), an analysis's relationship to its constituents is
deliberate and structural: "AAPL and MSFT are IN this correlation study" is
a fact about the analysis, not a coincidence of tagging. That's what the
`analysis_companies`/`analysis_references`/`analysis_links` join tables
capture — see `equity.ports.repository.AnalysisRepo`.

`kind` is free text, same "flexible now, curate later" philosophy as
`equity.domain.attributes` and `equity.domain.references`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Analysis:
    """One experimental workspace: a model, a study, an analysis in
    progress. `id`/timestamps are None until the repository persists it."""

    kind: str  # suggested vocabulary: "dcf-variant" | "portfolio" | "correlation-study" | "other"
    title: str
    summary: str = ""
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
