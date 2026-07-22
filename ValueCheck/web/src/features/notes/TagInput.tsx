import Fuse from "fuse.js";
import { useMemo, useState } from "react";

/**
 * Tag chips + input with fuzzy autocomplete over the canonical vocabulary
 * (fuse.js catches typos: "semicondctors" still suggests "semiconductors").
 * The SERVER canonicalizes on save — suggestions here are a typing aid only.
 */
export function TagInput({
  value,
  onChange,
  vocabulary,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
  vocabulary: string[];
}) {
  const [draft, setDraft] = useState("");

  const fuse = useMemo(
    () => new Fuse(vocabulary, { threshold: 0.4, ignoreLocation: true }),
    [vocabulary],
  );

  const suggestions = useMemo(() => {
    if (!draft.trim()) return [];
    return fuse
      .search(draft.trim())
      .map((r) => r.item)
      .filter((tag) => !value.includes(tag))
      .slice(0, 6);
  }, [draft, fuse, value]);

  const add = (tag: string) => {
    const cleaned = tag.trim();
    if (!cleaned) return;
    if (!value.includes(cleaned)) onChange([...value, cleaned]);
    setDraft("");
  };

  const remove = (tag: string) => onChange(value.filter((t) => t !== tag));

  return (
    <div className="tag-input" data-testid="tag-input">
      <div className="tag-chips">
        {value.map((tag) => (
          <span key={tag} className="tag-chip">
            {tag}
            <button
              type="button"
              aria-label={`Remove tag ${tag}`}
              onClick={() => remove(tag)}
            >
              ×
            </button>
          </span>
        ))}
        <input
          value={draft}
          placeholder={value.length === 0 ? "Add tags…" : ""}
          aria-label="Add tag"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add(suggestions[0] && draft !== suggestions[0] ? suggestions[0] : draft);
            } else if (e.key === "Backspace" && draft === "" && value.length > 0) {
              remove(value[value.length - 1]);
            }
          }}
        />
      </div>
      {suggestions.length > 0 && (
        <ul className="tag-suggestions" role="listbox" aria-label="Tag suggestions">
          {suggestions.map((tag) => (
            <li key={tag}>
              <button type="button" role="option" aria-selected={false} onClick={() => add(tag)}>
                {tag}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
