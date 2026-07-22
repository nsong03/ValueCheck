import { useState } from "react";

import type { NoteOut, NoteUpdate } from "../../api/client";
import { TagInput } from "./TagInput";

/** Create/edit form for one note. Tags are canonicalized by the server on
 * save; the editor shows whatever the user typed until then. */
export function NoteEditor({
  initial,
  vocabulary,
  onSave,
  onCancel,
  saving,
}: {
  initial: NoteOut | null;
  vocabulary: string[];
  onSave: (note: NoteUpdate) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [body, setBody] = useState(initial?.body ?? "");
  const [tags, setTags] = useState<string[]>(initial?.tags ?? []);

  return (
    <form
      className="note-editor"
      data-testid="note-editor"
      onSubmit={(e) => {
        e.preventDefault();
        if (title.trim()) onSave({ title: title.trim(), body, tags });
      }}
    >
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Note title"
        aria-label="Note title"
        required
      />
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Your research — what did the filings tell you?"
        aria-label="Note body"
        rows={5}
      />
      <TagInput value={tags} onChange={setTags} vocabulary={vocabulary} />
      <div className="note-editor-actions">
        <button type="submit" disabled={saving || !title.trim()}>
          {saving ? "Saving…" : initial ? "Save changes" : "Add note"}
        </button>
        <button type="button" className="ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
