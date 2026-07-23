-- Canonical CURRENT schema (reference). The database is built by applying
-- adapters/persistence/migrations/*.sql in order; an integration test asserts
-- this file stays in sync with the migration result. All timestamps are ISO
-- 8601 UTC strings; monetary values in $ millions (BUILD_SPEC §5).

CREATE TABLE schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL
);

CREATE TABLE companies (
    ticker      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    sector      TEXT NOT NULL DEFAULT 'Unknown',
    industry    TEXT NOT NULL DEFAULT 'Unknown',
    sic         TEXT,
    total_debt  REAL NOT NULL DEFAULT 0,
    cash        REAL NOT NULL DEFAULT 0,
    shares_out  REAL NOT NULL DEFAULT 0,
    price       REAL NOT NULL DEFAULT 0,
    beta        REAL NOT NULL DEFAULT 1.0,
    fetched_at  TEXT NOT NULL
);

-- One row per (ticker, fiscal year, metric): the normalized history series.
CREATE TABLE financial_facts (
    ticker      TEXT NOT NULL REFERENCES companies(ticker) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    metric      TEXT NOT NULL CHECK (metric IN
                    ('revenue', 'ebit', 'da', 'capex', 'nwc', 'tax_rate')),
    value       REAL NOT NULL,
    PRIMARY KEY (ticker, fiscal_year, metric)
);

-- Audit trail: every external datum links back to its origin (directive #4).
CREATE TABLE source_links (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT NOT NULL REFERENCES companies(ticker) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    label       TEXT NOT NULL,
    url         TEXT NOT NULL DEFAULT '',
    accession   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_source_links_ticker ON source_links(ticker);

CREATE TABLE valuations (
    id                   INTEGER PRIMARY KEY,
    ticker               TEXT NOT NULL REFERENCES companies(ticker) ON DELETE CASCADE,
    created_at           TEXT NOT NULL,
    wacc                 REAL NOT NULL,
    enterprise_value     REAL,               -- NULL = NaN (incomputable, e.g. g >= WACC)
    equity_value         REAL,               -- NULL = NaN
    fair_value_per_share REAL,               -- NULL = NaN (no share count)
    upside               REAL,               -- NULL = NaN (no market price)
    assumptions_json     TEXT NOT NULL,
    projection_json      TEXT NOT NULL,
    warnings_json        TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX idx_valuations_ticker ON valuations(ticker, created_at DESC);

-- The knowledge library (0004): books, articles, PDFs, webpages.
CREATE TABLE reference_items (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,
    title       TEXT NOT NULL,
    location    TEXT NOT NULL,
    collection  TEXT NOT NULL DEFAULT '',
    origin      TEXT NOT NULL CHECK (origin IN ('manual', 'scan')),
    added_at    TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_reference_items_location ON reference_items(location);
CREATE INDEX idx_reference_items_collection ON reference_items(collection);

-- The balcony (0005): analyses (financial models, portfolio constructions,
-- correlation studies) with EXPLICIT links to companies/references/other
-- analyses — structural facts about the analysis, distinct from tag-based
-- (incidental) association.
CREATE TABLE analyses (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- No ticker FK (same freedom as `notes`).
CREATE TABLE analysis_companies (
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    ticker      TEXT NOT NULL,
    PRIMARY KEY (analysis_id, ticker)
);
CREATE INDEX idx_analysis_companies_ticker ON analysis_companies(ticker);

CREATE TABLE analysis_references (
    analysis_id  INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    reference_id INTEGER NOT NULL REFERENCES reference_items(id) ON DELETE CASCADE,
    PRIMARY KEY (analysis_id, reference_id)
);
CREATE INDEX idx_analysis_references_reference ON analysis_references(reference_id);

-- Directed: `analysis_id` references `linked_analysis_id`.
CREATE TABLE analysis_links (
    analysis_id        INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    linked_analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    PRIMARY KEY (analysis_id, linked_analysis_id),
    CHECK (analysis_id <> linked_analysis_id)
);

-- A note attaches to a company, a reference, or an analysis (0005: exactly
-- one of the three is set).
CREATE TABLE notes (
    id           INTEGER PRIMARY KEY,
    ticker       TEXT,
    reference_id INTEGER REFERENCES reference_items(id) ON DELETE CASCADE,
    analysis_id  INTEGER REFERENCES analyses(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL DEFAULT '',
    links_json   TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    CHECK (
        (CASE WHEN ticker IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN reference_id IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN analysis_id IS NOT NULL THEN 1 ELSE 0 END) = 1
    )
);
CREATE INDEX idx_notes_ticker ON notes(ticker, created_at DESC);
CREATE INDEX idx_notes_reference ON notes(reference_id, created_at DESC);
CREATE INDEX idx_notes_analysis ON notes(analysis_id, created_at DESC);

CREATE TABLE tags (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE note_tags (
    note_id  INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id)
);

-- Full-text search over notes (0002). External-content FTS5; kept in sync by
-- triggers so the index can never drift from the notes table.
CREATE VIRTUAL TABLE notes_fts USING fts5(
    title,
    body,
    content='notes',
    content_rowid='id'
);

CREATE TRIGGER notes_fts_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;

CREATE TRIGGER notes_fts_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, body)
        VALUES ('delete', old.id, old.title, old.body);
END;

CREATE TRIGGER notes_fts_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, body)
        VALUES ('delete', old.id, old.title, old.body);
    INSERT INTO notes_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;

-- Research attributes (0003): typed, namespaced company facts (region,
-- custom sector, quality scores, status), with full append-only history.
CREATE TABLE attribute_definitions (
    key                 TEXT PRIMARY KEY,
    label               TEXT NOT NULL,
    value_type          TEXT NOT NULL DEFAULT 'text'
                            CHECK (value_type IN ('text', 'number', 'scale')),
    scale_min           REAL,
    scale_max           REAL,
    allowed_values_json TEXT,
    colors_json         TEXT,
    created_at          TEXT NOT NULL
);

-- No ticker FK (same freedom as `notes`); `key` references a definition.
CREATE TABLE company_attribute_history (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT NOT NULL,
    key         TEXT NOT NULL REFERENCES attribute_definitions(key) ON DELETE CASCADE,
    value       TEXT NOT NULL,
    source      TEXT NOT NULL CHECK (source IN ('note', 'grid')),
    note_id     INTEGER REFERENCES notes(id) ON DELETE SET NULL,
    reason      TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_attr_history_ticker_key ON company_attribute_history(ticker, key, created_at DESC);
