-- Migration 0005: the balcony (Phase 9c) — analyses (financial models,
-- portfolio constructions, correlation studies) with EXPLICIT links to the
-- companies/references/other analyses they draw on. Distinct from tag-based
-- association: a shared tag is incidental, these links are structural facts
-- about the analysis. Also generalizes `notes` to a third optional subject.

CREATE TABLE analyses (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,               -- free text: "dcf-variant" | "portfolio" | "correlation-study" | "other"
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- No ticker FK (same freedom as `notes`/`company_attribute_history`).
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

-- Directed: `analysis_id` references `linked_analysis_id`. The graph renders
-- these as plain edges regardless of direction; the direction is kept for
-- "what does THIS build on" vs "what builds on THIS" reverse lookups.
CREATE TABLE analysis_links (
    analysis_id        INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    linked_analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    PRIMARY KEY (analysis_id, linked_analysis_id),
    CHECK (analysis_id <> linked_analysis_id)
);

-- Rebuild `notes` again: `analysis_id` is the third optional subject
-- (exactly one of ticker/reference_id/analysis_id). Same rebuild pattern as
-- 0004 — `id` values preserved, FTS triggers recreated.
--
-- Same caution as 0004: dropping `notes` below cascades its children's ON
-- DELETE actions (this fires for DROP TABLE, not just real DELETEs), which
-- would silently wipe `note_tags` (ON DELETE CASCADE) and null out
-- `company_attribute_history.note_id` (ON DELETE SET NULL). Back both up,
-- restore after.
CREATE TABLE _note_tags_backup AS SELECT * FROM note_tags;
CREATE TABLE _attr_note_id_backup AS
    SELECT id, note_id FROM company_attribute_history WHERE note_id IS NOT NULL;

CREATE TABLE notes_new (
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
INSERT INTO notes_new
    (id, ticker, reference_id, analysis_id, title, body, links_json, created_at, updated_at)
    SELECT id, ticker, reference_id, NULL, title, body, links_json, created_at, updated_at
    FROM notes;
DROP TABLE notes;
ALTER TABLE notes_new RENAME TO notes;

CREATE INDEX idx_notes_ticker ON notes(ticker, created_at DESC);
CREATE INDEX idx_notes_reference ON notes(reference_id, created_at DESC);
CREATE INDEX idx_notes_analysis ON notes(analysis_id, created_at DESC);

INSERT INTO note_tags SELECT * FROM _note_tags_backup;
DROP TABLE _note_tags_backup;

UPDATE company_attribute_history
    SET note_id = (
        SELECT note_id FROM _attr_note_id_backup
        WHERE _attr_note_id_backup.id = company_attribute_history.id
    )
    WHERE id IN (SELECT id FROM _attr_note_id_backup);
DROP TABLE _attr_note_id_backup;

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
