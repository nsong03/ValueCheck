-- Migration 0004: the knowledge library (Phase 9b). Adds `reference_items`
-- (books/PDFs/articles/webpages) and generalizes `notes` so a note attaches
-- to a company OR a reference (exactly one), and can carry structured inline
-- links. Same tags/note_tags/notes_fts machinery covers both — nothing about
-- those tables changes.

CREATE TABLE reference_items (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,               -- free text: "pdf" | "webpage" | "book" | "article" | "other"
    title       TEXT NOT NULL,
    location    TEXT NOT NULL,               -- absolute file path or URL
    collection  TEXT NOT NULL DEFAULT '',     -- folder-derived path, e.g. "TechnicalReading/Valuation"
    origin      TEXT NOT NULL CHECK (origin IN ('manual', 'scan')),
    added_at    TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_reference_items_location ON reference_items(location);
CREATE INDEX idx_reference_items_collection ON reference_items(collection);

-- Rebuild `notes`: `ticker` becomes optional, `reference_id` is the new
-- optional subject (exactly one of the two is set), `links_json` carries
-- inline link chips. `id` values are copied unchanged so `notes_fts`
-- (external content, content_rowid='id') stays valid with no rebuild of its
-- own — only the FTS triggers need recreating, since SQLite drops triggers
-- when their target table is dropped.
--
-- CAUTION (found the hard way): with `PRAGMA foreign_keys = ON`, dropping a
-- table cascades its children's ON DELETE actions too — not just real DELETE
-- statements. `note_tags.note_id ... ON DELETE CASCADE` would have every row
-- silently deleted (tags wiped) and `company_attribute_history.note_id ...
-- ON DELETE SET NULL` would have every note_id nulled (provenance lost) the
-- instant `DROP TABLE notes` runs below. Back both up first, restore after.
CREATE TABLE _note_tags_backup AS SELECT * FROM note_tags;
CREATE TABLE _attr_note_id_backup AS
    SELECT id, note_id FROM company_attribute_history WHERE note_id IS NOT NULL;

CREATE TABLE notes_new (
    id           INTEGER PRIMARY KEY,
    ticker       TEXT,
    reference_id INTEGER REFERENCES reference_items(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL DEFAULT '',
    links_json   TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    CHECK ((ticker IS NOT NULL) <> (reference_id IS NOT NULL))
);
INSERT INTO notes_new (id, ticker, reference_id, title, body, links_json, created_at, updated_at)
    SELECT id, ticker, NULL, title, body, '[]', created_at, updated_at FROM notes;
DROP TABLE notes;
ALTER TABLE notes_new RENAME TO notes;

CREATE INDEX idx_notes_ticker ON notes(ticker, created_at DESC);
CREATE INDEX idx_notes_reference ON notes(reference_id, created_at DESC);

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
