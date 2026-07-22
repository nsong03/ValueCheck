"""Search port: full-text queries over research notes.

Phase 8's use-case: "an event happened — which of my companies are impacted?"
The index implementation (FTS5) lives in adapters; keeping it behind a port
means Postgres tsvector (or an external engine) later is a swap.
"""

from __future__ import annotations

from typing import Protocol

from equity.domain.research import SearchHit


class SearchIndex(Protocol):
    def search_notes(self, query: str, limit: int = 50) -> list[SearchHit]:
        """Best-first full-text matches over note titles + bodies.

        Implementations must tolerate arbitrary user input (punctuation,
        quotes, operators) without raising; an unmatchable query returns [].
        """
        ...
