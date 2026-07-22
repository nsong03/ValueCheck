import { useState } from "react";

import { useSearch } from "../../api/hooks";

/** Event search: free text -> matching notes + impacted tickers.
 * "chip shortage" -> which covered companies does my research say it touches? */
export function SearchPanel({
  onOpenCompany,
  onImpacted,
}: {
  onOpenCompany: (ticker: string) => void;
  onImpacted: (tickers: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const [submitted, setSubmitted] = useState<string | null>(null);
  const search = useSearch(submitted);

  return (
    <section className="search-panel" data-testid="search-panel">
      <form
        className="search-form"
        onSubmit={(e) => {
          e.preventDefault();
          const q = draft.trim();
          if (q) setSubmitted(q);
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder='Search your research — e.g. "chip shortage"'
          aria-label="Search notes"
        />
        <button type="submit">Search</button>
      </form>

      {search.isFetching && <p className="status">Searching…</p>}
      {search.isError && (
        <div className="error-banner" role="alert">
          Search failed: {String(search.error)}
        </div>
      )}
      {search.data && !search.isFetching && (
        <div className="search-results" data-testid="search-results">
          {search.data.impacted_tickers.length === 0 ? (
            <p className="subtle">No notes match &ldquo;{search.data.query}&rdquo;.</p>
          ) : (
            <>
              <p className="subtle">
                Impacted companies for &ldquo;{search.data.query}&rdquo;:
                {"  "}
                {search.data.impacted_tickers.map((t) => (
                  <button
                    key={t}
                    type="button"
                    className="ticker-pill"
                    onClick={() => onOpenCompany(t)}
                  >
                    {t}
                  </button>
                ))}
                <button
                  type="button"
                  className="ghost"
                  onClick={() => onImpacted(search.data.impacted_tickers)}
                >
                  View as graph →
                </button>
              </p>
              <ul className="hit-list">
                {search.data.hits.map((h) => (
                  <li key={h.note_id}>
                    <strong>{h.ticker}</strong> · {h.title} —{" "}
                    <span
                      className="snippet"
                      // snippet highlighting uses plain [brackets], no HTML
                    >
                      {h.snippet}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}
