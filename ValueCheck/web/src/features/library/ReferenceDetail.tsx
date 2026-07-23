import { useState } from "react";

import { api, ApiError } from "../../api/client";
import {
  useAnalysesForReference,
  useDeleteReference,
  useReference,
  useUpdateReference,
} from "../../api/hooks";
import { NotesSection } from "../notes/NotesSection";

/** One reference: editable metadata, a link to open the underlying file/URL,
 * which analyses (models/studies) cite it, and its own notes. */
export function ReferenceDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const reference = useReference(id);
  const update = useUpdateReference();
  const remove = useDeleteReference();
  const citedBy = useAnalysesForReference(id);
  const [editingTitle, setEditingTitle] = useState(false);
  const [title, setTitle] = useState("");

  if (reference.isPending) return <p className="status">Loading…</p>;
  if (reference.isError) {
    return (
      <div className="error-banner" role="alert">
        Couldn&apos;t load reference: {String(reference.error)}
      </div>
    );
  }
  const ref = reference.data;
  const isUrl = ref.location.startsWith("http://") || ref.location.startsWith("https://");

  return (
    <div className="workspace">
      <button type="button" className="ghost" onClick={onBack}>
        ← Back to library
      </button>

      <section className="company-header">
        <div>
          {editingTitle ? (
            <input
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={() => {
                setEditingTitle(false);
                if (title.trim() && title !== ref.title) {
                  update.mutate({ id: ref.id, patch: { title: title.trim() } });
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
              aria-label="Reference title"
            />
          ) : (
            <h2
              onClick={() => {
                setTitle(ref.title);
                setEditingTitle(true);
              }}
            >
              {ref.title} <span className="ticker-chip">{ref.kind}</span>
            </h2>
          )}
          <p className="subtle">
            {ref.collection || "(uncategorized)"} · added{" "}
            {new Date(ref.added_at).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}{" "}
            · {ref.origin}
          </p>
        </div>
        <div className="key-stats">
          <a
            className="ticker-pill"
            href={isUrl ? ref.location : api.referenceFileUrl(ref.id)}
            target="_blank"
            rel="noreferrer"
          >
            Open {isUrl ? "link" : "file"} →
          </a>
          <button
            type="button"
            className="ghost danger"
            onClick={() => {
              if (confirm(`Delete "${ref.title}"? This also deletes its notes.`)) {
                remove.mutate(ref.id, { onSuccess: onBack });
              }
            }}
          >
            Delete
          </button>
        </div>
      </section>

      {citedBy.data && citedBy.data.length > 0 && (
        <section>
          <h3>Cited by</h3>
          <ul className="reference-list">
            {citedBy.data.map((a) => (
              <li key={a.id}>
                <span className="tag-chip readonly">{a.kind}</span> {a.title}
              </li>
            ))}
          </ul>
        </section>
      )}

      {update.isError && (
        <div className="error-banner" role="alert">
          {update.error instanceof ApiError
            ? `${update.error.message} (${update.error.code})`
            : String(update.error)}
        </div>
      )}

      <NotesSection subject={{ kind: "reference", id: ref.id }} />
    </div>
  );
}
