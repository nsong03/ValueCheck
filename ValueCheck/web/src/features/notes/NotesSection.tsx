import { useState } from "react";

import type { NoteOut } from "../../api/client";
import { useDeleteNote, useNotes, useSaveNote, useTags } from "../../api/hooks";
import { NoteEditor } from "./NoteEditor";

export function NotesSection({ ticker }: { ticker: string }) {
  const notes = useNotes(ticker);
  const tags = useTags();
  const save = useSaveNote(ticker);
  const remove = useDeleteNote(ticker);
  // null = closed, "new" = creating, NoteOut = editing that note
  const [editing, setEditing] = useState<"new" | NoteOut | null>(null);

  const vocabulary = tags.data?.tags ?? [];

  return (
    <section data-testid="notes-section">
      <div className="notes-head">
        <h3>Research notes</h3>
        {editing === null && (
          <button type="button" onClick={() => setEditing("new")}>
            New note
          </button>
        )}
      </div>

      {editing !== null && (
        <NoteEditor
          initial={editing === "new" ? null : editing}
          vocabulary={vocabulary}
          saving={save.isPending}
          onCancel={() => setEditing(null)}
          onSave={(payload) => {
            save.mutate(
              { id: editing === "new" ? null : editing.id, note: payload },
              { onSuccess: () => setEditing(null) },
            );
          }}
        />
      )}
      {save.isError && (
        <div className="error-banner" role="alert">
          Couldn&apos;t save note: {String(save.error)}
        </div>
      )}

      {notes.isPending ? (
        <p className="status">Loading notes…</p>
      ) : notes.isError ? (
        <div className="error-banner" role="alert">
          Couldn&apos;t load notes: {String(notes.error)}
        </div>
      ) : notes.data.length === 0 && editing === null ? (
        <p className="subtle">No notes yet — capture your thesis alongside the numbers.</p>
      ) : (
        <ul className="note-list">
          {notes.data.map((note) => (
            <li key={note.id} className="note-card">
              <div className="note-card-head">
                <strong>{note.title}</strong>
                <span className="note-actions">
                  <button type="button" className="ghost" onClick={() => setEditing(note)}>
                    Edit
                  </button>
                  <button
                    type="button"
                    className="ghost danger"
                    onClick={() => remove.mutate(note.id)}
                  >
                    Delete
                  </button>
                </span>
              </div>
              {note.body && <p className="note-body">{note.body}</p>}
              <div className="note-meta">
                {note.tags.map((tag) => (
                  <span key={tag} className="tag-chip readonly">
                    {tag}
                  </span>
                ))}
                <span className="subtle">
                  {new Date(note.updated_at).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
