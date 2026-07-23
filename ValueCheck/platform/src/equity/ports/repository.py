"""Repository ports: persistence interfaces for the application layer.

Adapters (Phase 3: raw-SQL SQLite) implement these. Postgres later is a swap
behind the same ports (BUILD_SPEC §8). Implementations raise
`equity.errors.PersistenceError` on storage failures (e.g. saving a valuation
for an unknown company); "not found" is `None`/`False`, not an exception.
"""

from __future__ import annotations

from typing import Protocol

from equity.domain.analysis import Analysis
from equity.domain.attributes import AttributeDefinition, AttributeValue
from equity.domain.models import CompanyFinancials
from equity.domain.references import Reference
from equity.domain.research import Note
from equity.domain.valuation import DCFResult, ValuationRecord


class CompanyRepo(Protocol):
    """Stores normalized company financials (the ingestion cache)."""

    def save(self, fin: CompanyFinancials) -> None:
        """Insert or fully replace the company keyed by ticker (upsert)."""
        ...

    def get(self, ticker: str) -> CompanyFinancials | None: ...

    def list_tickers(self) -> list[str]: ...

    def delete(self, ticker: str) -> bool:
        """Remove a company and its dependent rows. True if it existed."""
        ...


class ValuationRepo(Protocol):
    """Stores completed DCF runs, newest first."""

    def save(self, result: DCFResult) -> ValuationRecord:
        """Persist a run for `result.fin.ticker`; returns the stored record
        with its assigned id and timestamp. The company must already exist."""
        ...

    def get(self, valuation_id: int) -> ValuationRecord | None: ...

    def list_for(self, ticker: str) -> list[ValuationRecord]: ...


class NoteRepo(Protocol):
    """Stores research notes with their tags. A note attaches to a company,
    a reference, or an analysis — exactly one of `ticker`/`reference_id`/
    `analysis_id` is set."""

    def save(self, note: Note) -> Note:
        """Insert (id None) or update (id set); returns the stored note with
        id and timestamps assigned. Tags are replaced wholesale on update."""
        ...

    def get(self, note_id: int) -> Note | None: ...

    def list_for(self, ticker: str) -> list[Note]: ...

    def list_for_reference(self, reference_id: int) -> list[Note]: ...

    def list_for_analysis(self, analysis_id: int) -> list[Note]: ...

    def delete(self, note_id: int) -> bool: ...


class TagRepo(Protocol):
    """The tag vocabulary (individual tag writes happen via NoteRepo.save)."""

    def all_tags(self) -> list[str]:
        """Every distinct tag name in use, sorted, for autocomplete."""
        ...

    def merge(self, source: str, target: str) -> int:
        """Retag every note carrying `source` to `target` (atomically) and
        drop `source` from the vocabulary. Returns the number of notes whose
        tags changed; 0 when `source` is unused/unknown."""
        ...


class AttributeRepo(Protocol):
    """Typed, namespaced company facts with full history (Phase 9).

    Unlike Company/Valuation, a `ticker` here need not already exist in the
    companies table — same freedom notes already have — so research can be
    tagged onto a company before (or without) ever running a valuation on it.
    """

    def get_definition(self, key: str) -> AttributeDefinition | None: ...

    def upsert_definition(self, definition: AttributeDefinition) -> AttributeDefinition:
        """Insert or fully replace the definition for `definition.key`."""
        ...

    def list_definitions(self) -> list[AttributeDefinition]:
        """Every known attribute key, sorted, for the UI's key picker/columns."""
        ...

    def append_value(self, value: AttributeValue) -> AttributeValue:
        """Append one historical entry; returns it with id + created_at set.
        `value.key` must already have a definition (FK-enforced by adapters)."""
        ...

    def history_for(self, ticker: str, key: str) -> list[AttributeValue]:
        """Every value ever recorded for (ticker, key), newest first."""
        ...

    def current_for(self, ticker: str) -> dict[str, AttributeValue]:
        """The latest value per key for one company, keyed by attribute key."""
        ...


class ReferenceRepo(Protocol):
    """Stores the knowledge library: books, articles, PDFs, webpages."""

    def save(self, reference: Reference) -> Reference:
        """Insert (id None) or update (id set); returns it with id/added_at
        assigned. `location` is unique — inserting a duplicate is a conflict,
        not silently ignored (surfaced by the service as `ConflictError`)."""
        ...

    def get(self, reference_id: int) -> Reference | None: ...

    def get_by_location(self, location: str) -> Reference | None:
        """Look up by exact location (URL or path); used to dedupe a scan."""
        ...

    def list_all(self) -> list[Reference]: ...

    def delete(self, reference_id: int) -> bool: ...


class AnalysisRepo(Protocol):
    """Stores analyses (models/studies, Phase 9c) and their EXPLICIT links
    to companies, references, and other analyses.

    This is deliberately distinct from tag-based association: a shared tag
    between a note and an analysis is incidental ("both happen to mention
    value-investing"), but these links are structural facts about the
    analysis itself ("AAPL IS a constituent of this correlation study").
    Reverse lookups (`list_for_company`/`list_for_reference`) are what let
    you later ask "what models have I built that touch this stock?"
    """

    def save(self, analysis: Analysis) -> Analysis:
        """Insert (id None) or update (id set); returns it with id/timestamps
        assigned."""
        ...

    def get(self, analysis_id: int) -> Analysis | None: ...

    def list_all(self) -> list[Analysis]: ...

    def delete(self, analysis_id: int) -> bool:
        """Remove an analysis and its links/notes (cascade). True if it existed."""
        ...

    # -- company constituents ---------------------------------------------
    def add_company(self, analysis_id: int, ticker: str) -> None:
        """Idempotent: linking an already-linked ticker is a no-op."""
        ...

    def remove_company(self, analysis_id: int, ticker: str) -> None: ...

    def list_companies(self, analysis_id: int) -> list[str]:
        """Tickers explicitly linked to this analysis, sorted."""
        ...

    def list_for_company(self, ticker: str) -> list[Analysis]:
        """Every analysis that explicitly includes this ticker."""
        ...

    # -- reference constituents --------------------------------------------
    def add_reference(self, analysis_id: int, reference_id: int) -> None:
        """Idempotent: linking an already-linked reference is a no-op."""
        ...

    def remove_reference(self, analysis_id: int, reference_id: int) -> None: ...

    def list_references(self, analysis_id: int) -> list[int]:
        """Reference ids explicitly linked to this analysis, sorted."""
        ...

    def list_for_reference(self, reference_id: int) -> list[Analysis]:
        """Every analysis that explicitly cites this reference."""
        ...

    # -- analysis <-> analysis (directed: this analysis references another) --
    def add_link(self, analysis_id: int, linked_analysis_id: int) -> None:
        """Idempotent. Self-links (analysis_id == linked_analysis_id) are
        rejected by the service, not the repo."""
        ...

    def remove_link(self, analysis_id: int, linked_analysis_id: int) -> None: ...

    def list_links(self, analysis_id: int) -> list[int]:
        """Ids of analyses this one explicitly links to (outgoing), sorted."""
        ...
