"""Repository ports: persistence interfaces for the application layer.

Adapters (Phase 3: raw-SQL SQLite) implement these. Postgres later is a swap
behind the same ports (BUILD_SPEC §8). Implementations raise
`equity.errors.PersistenceError` on storage failures (e.g. saving a valuation
for an unknown company); "not found" is `None`/`False`, not an exception.
"""

from __future__ import annotations

from typing import Protocol

from equity.domain.models import CompanyFinancials
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
    """Stores research notes with their tags."""

    def save(self, note: Note) -> Note:
        """Insert (id None) or update (id set); returns the stored note with
        id and timestamps assigned. Tags are replaced wholesale on update."""
        ...

    def get(self, note_id: int) -> Note | None: ...

    def list_for(self, ticker: str) -> list[Note]: ...

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
