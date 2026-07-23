import { useState } from "react";

import type { NoteLinkIn, NoteOut, NoteUpdate } from "../../api/client";
import { TagInput } from "./TagInput";

/** Create/edit form for one note. Tags are canonicalized by the server on
 * save; the editor shows whatever the user typed until then. Links are
 * inline citations — a web URL or a path on this machine — carried
 * alongside the note regardless of what it's about (company/reference/
 * analysis). */
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
  const [links, setLinks] = useState<NoteLinkIn[]>(initial?.links ?? []);
  const [linkLabel, setLinkLabel] = useState("");
  const [linkUrl, setLinkUrl] = useState("");

  const addLink = () => {
    const label = linkLabel.trim();
    const url = linkUrl.trim();
    if (!label || !url) return;
    setLinks((prev) => [...prev, { label, url }]);
    setLinkLabel("");
    setLinkUrl("");
  };

  return (
    <form
      className="note-editor"
      data-testid="note-editor"
      onSubmit={(e) => {
        e.preventDefault();
        if (title.trim()) onSave({ title: title.trim(), body, tags, links });
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

      <div className="links-input" data-testid="links-input">
        <div className="link-chips">
          {links.map((link, i) => (
            <span key={`${link.url}-${i}`} className="link-chip">
              <a href={link.url} target="_blank" rel="noreferrer">
                {link.label}
              </a>
              <button
                type="button"
                aria-label={`Remove link ${link.label}`}
                onClick={() => setLinks((prev) => prev.filter((_, j) => j !== i))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <div className="link-add-row">
          <input
            value={linkLabel}
            onChange={(e) => setLinkLabel(e.target.value)}
            placeholder="Link label"
            aria-label="Link label"
          />
          <input
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://… or a local file path"
            aria-label="Link URL"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addLink();
              }
            }}
          />
          <button type="button" className="ghost" onClick={addLink}>
            Add link
          </button>
        </div>
      </div>

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
