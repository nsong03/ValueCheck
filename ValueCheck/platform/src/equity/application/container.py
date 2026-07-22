"""Composition root: the ONE place ports are bound to concrete adapters.

Everything below the API layer receives its dependencies from here; nothing
else constructs adapters. Tests (and offline mode) pass overrides instead of
monkeypatching. Swapping SQLite for Postgres, or yfinance for another feed,
is a change to this module only (BUILD_SPEC §8).
"""

from __future__ import annotations

from dataclasses import dataclass

from equity.adapters.filings.edgar import EdgarFilingsSource
from equity.adapters.market.yfinance import YFinanceProvider
from equity.adapters.persistence.sqlite import (
    SQLiteCompanyRepo,
    SQLiteDatabase,
    SQLiteNoteRepo,
    SQLiteTagRepo,
    SQLiteValuationRepo,
)
from equity.application.ingestion_service import IngestionService
from equity.application.valuation_service import ValuationService
from equity.config import Settings, get_settings
from equity.logging import get_logger
from equity.ports.filings import FilingsProvider
from equity.ports.market import MarketDataProvider
from equity.ports.repository import CompanyRepo, NoteRepo, TagRepo, ValuationRepo

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Container:
    """Wired application object graph for one process."""

    settings: Settings
    db: SQLiteDatabase
    companies: CompanyRepo
    valuations: ValuationRepo
    notes: NoteRepo
    tags: TagRepo
    filings: FilingsProvider
    market: MarketDataProvider
    ingestion: IngestionService
    valuation: ValuationService


def build_container(
    settings: Settings | None = None,
    *,
    filings: FilingsProvider | None = None,
    market: MarketDataProvider | None = None,
) -> Container:
    """Build the object graph from settings, applying migrations on the way.

    `filings`/`market` overrides exist for tests and offline demos; defaults
    are the live adapters (EDGAR identity is validated lazily at fetch time,
    so a container without EQUITY_EDGAR_IDENTITY still serves cached data).
    """
    settings = settings or get_settings()

    db = SQLiteDatabase(settings.database_path)
    db.migrate()

    companies = SQLiteCompanyRepo(db)
    valuations = SQLiteValuationRepo(db)
    notes = SQLiteNoteRepo(db)
    tags = SQLiteTagRepo(db)

    filings = filings if filings is not None else EdgarFilingsSource(settings.edgar_identity)
    market = market if market is not None else YFinanceProvider()

    ingestion = IngestionService(companies, filings, market)
    valuation = ValuationService(ingestion, valuations)

    log.info(
        "container.built",
        database=str(settings.database_path),
        filings=type(filings).__name__,
        market=type(market).__name__,
    )
    return Container(
        settings=settings,
        db=db,
        companies=companies,
        valuations=valuations,
        notes=notes,
        tags=tags,
        filings=filings,
        market=market,
        ingestion=ingestion,
        valuation=valuation,
    )
