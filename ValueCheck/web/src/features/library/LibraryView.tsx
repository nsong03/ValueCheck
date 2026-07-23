import { useMemo, useState } from "react";

import { ApiError, type ReferenceOut } from "../../api/client";
import { useCreateReference, useReferences, useScanReferences } from "../../api/hooks";
import { ReferenceDetail } from "./ReferenceDetail";

function AddReferenceForm({ onCreated }: { onCreated: (id: number) => void }) {
  const create = useCreateReference();
  const [kind, setKind] = useState("webpage");
  const [title, setTitle] = useState("");
  const [location, setLocation] = useState("");
  const [collection, setCollection] = useState("");

  return (
    <form
      className="reference-add-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (!title.trim() || !location.trim()) return;
        create.mutate(
          { kind, title: title.trim(), location: location.trim(), collection: collection.trim() },
          {
            onSuccess: (ref) => {
              setTitle("");
              setLocation("");
              onCreated(ref.id);
            },
          },
        );
      }}
    >
      <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Reference kind">
        <option value="webpage">webpage</option>
        <option value="article">article</option>
        <option value="book">book</option>
        <option value="pdf">pdf</option>
        <option value="other">other</option>
      </select>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title"
        aria-label="Reference title"
      />
      <input
        value={location}
        onChange={(e) => setLocation(e.target.value)}
        placeholder="URL or local file path"
        aria-label="Reference location"
      />
      <input
        value={collection}
        onChange={(e) => setCollection(e.target.value)}
        placeholder="Collection (optional)"
        aria-label="Reference collection"
      />
      <button type="submit" disabled={create.isPending || !title.trim() || !location.trim()}>
        Add
      </button>
      {create.isError && (
        <span className="error-banner" role="alert">
          {create.error instanceof ApiError
            ? `${create.error.message} (${create.error.code})`
            : String(create.error)}
        </span>
      )}
    </form>
  );
}

/** The knowledge library: books, articles, PDFs, webpages. PDFs dropped into
 * the configured folder show up automatically (scanned at server startup);
 * "Scan library" picks up anything added since. `selected`/`onSelect` are
 * controlled from above so a graph-node click can jump straight to a
 * reference's detail even from a different view. */
export function LibraryView({
  selected,
  onSelect,
}: {
  selected: number | null;
  onSelect: (id: number | null) => void;
}) {
  const references = useReferences();
  const scan = useScanReferences();
  const [collectionFilter, setCollectionFilter] = useState("");

  const grouped = useMemo(() => {
    const all = references.data ?? [];
    const filtered = collectionFilter
      ? all.filter((r) => r.collection === collectionFilter)
      : all;
    const groups = new Map<string, ReferenceOut[]>();
    for (const ref of filtered) {
      const key = ref.collection || "(uncategorized)";
      groups.set(key, [...(groups.get(key) ?? []), ref]);
    }
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [references.data, collectionFilter]);

  const collections = useMemo(
    () => [...new Set((references.data ?? []).map((r) => r.collection).filter(Boolean))].sort(),
    [references.data],
  );

  if (selected !== null) {
    return <ReferenceDetail id={selected} onBack={() => onSelect(null)} />;
  }

  return (
    <section data-testid="library-view">
      <div className="screener-head">
        <h3>Library</h3>
        <button type="button" onClick={() => scan.mutate()} disabled={scan.isPending}>
          {scan.isPending ? "Scanning…" : "Scan library"}
        </button>
        {collections.length > 0 && (
          <select
            value={collectionFilter}
            onChange={(e) => setCollectionFilter(e.target.value)}
            aria-label="Filter by collection"
          >
            <option value="">All collections</option>
            {collections.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
      </div>

      {scan.isSuccess && scan.data.created.length > 0 && (
        <p className="subtle">Found {scan.data.created.length} new file(s).</p>
      )}
      {scan.isSuccess && scan.data.created.length === 0 && (
        <p className="subtle">No new files found.</p>
      )}

      <AddReferenceForm onCreated={onSelect} />

      {references.isError && (
        <div className="error-banner" role="alert">
          Couldn&apos;t load library: {String(references.error)}
        </div>
      )}
      {references.isPending ? (
        <p className="status">Loading library…</p>
      ) : grouped.length === 0 ? (
        <p className="subtle">
          Nothing here yet — add a link above, or configure a folder to scan for PDFs.
        </p>
      ) : (
        grouped.map(([collection, refs]) => (
          <div key={collection} className="reference-collection">
            <h4>{collection}</h4>
            <ul className="reference-list">
              {refs.map((ref) => (
                <li key={ref.id}>
                  <button type="button" className="ghost" onClick={() => onSelect(ref.id)}>
                    <span className="ticker-chip">{ref.kind}</span> {ref.title}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}
