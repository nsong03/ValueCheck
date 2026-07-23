-- Migration 0003: research attributes — typed, namespaced facts about a
-- company (region, custom sector, quality scores, status), with full
-- history. "Current value" for a (ticker, key) is the latest row by
-- created_at; there is no separate current-value table to keep in sync
-- (queried via a window function — see SQLiteAttributeRepo.current_for).

CREATE TABLE attribute_definitions (
    key                 TEXT PRIMARY KEY,
    label               TEXT NOT NULL,
    value_type          TEXT NOT NULL DEFAULT 'text'
                            CHECK (value_type IN ('text', 'number', 'scale')),
    scale_min           REAL,
    scale_max           REAL,
    allowed_values_json TEXT,     -- JSON array; NULL = free text, no curated domain
    colors_json         TEXT,     -- JSON object {value: color}; NULL = uncolored
    created_at          TEXT NOT NULL
);

-- Append-only: no ticker FK (same freedom as `notes` — you can tag a company
-- before ever ingesting/valuing it). `key` DOES reference a definition: every
-- value is created through the service, which upserts the definition first.
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
