"""Search use-case: event query -> matching notes -> impacted tickers.

"TSMC halts fab expansion" -> which of MY covered companies did I write
thesis notes about that this touches? Hits come from the SearchIndex port;
impacted tickers are deduped in best-match-first order.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from equity.domain.research import SearchHit
from equity.logging import get_logger
from equity.ports.search import SearchIndex

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SearchResult:
    query: str
    hits: list[SearchHit] = field(default_factory=list)
    impacted_tickers: list[str] = field(default_factory=list)  # best-first, unique


class SearchService:
    def __init__(self, index: SearchIndex) -> None:
        self._index = index

    def impacted(self, query: str, limit: int = 50) -> SearchResult:
        hits = self._index.search_notes(query, limit=limit)
        seen: dict[str, None] = {}
        for hit in hits:
            seen.setdefault(hit.ticker, None)
        result = SearchResult(query=query, hits=hits, impacted_tickers=list(seen))
        log.info(
            "search.impacted",
            query=query,
            hits=len(hits),
            tickers=result.impacted_tickers,
        )
        return result
