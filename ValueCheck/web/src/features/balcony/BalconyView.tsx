import { useState } from "react";

import { ApiError } from "../../api/client";
import { useAnalyses, useCreateAnalysis } from "../../api/hooks";
import { AnalysisDetail } from "./AnalysisDetail";

function CreateAnalysisForm({ onCreated }: { onCreated: (id: number) => void }) {
  const create = useCreateAnalysis();
  const [kind, setKind] = useState("portfolio");
  const [title, setTitle] = useState("");

  return (
    <form
      className="reference-add-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (!title.trim()) return;
        create.mutate(
          { kind, title: title.trim(), summary: "" },
          {
            onSuccess: (a) => {
              setTitle("");
              onCreated(a.id);
            },
          },
        );
      }}
    >
      <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Analysis kind">
        <option value="dcf-variant">dcf-variant</option>
        <option value="portfolio">portfolio</option>
        <option value="correlation-study">correlation-study</option>
        <option value="other">other</option>
      </select>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title (e.g. Semis vs. rates)"
        aria-label="Analysis title"
      />
      <button type="submit" disabled={create.isPending || !title.trim()}>
        New analysis
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

/** The balcony: experimental analysis — financial models, portfolio
 * constructions, correlation studies — that explicitly link to the
 * companies and references they draw on. `selected`/`onSelect` are
 * controlled from above so a graph-node click can jump straight to an
 * analysis's detail even from a different view. */
export function BalconyView({
  selected,
  onSelect,
}: {
  selected: number | null;
  onSelect: (id: number | null) => void;
}) {
  const analyses = useAnalyses();

  if (selected !== null) {
    return <AnalysisDetail id={selected} onBack={() => onSelect(null)} />;
  }

  return (
    <section data-testid="balcony-view">
      <div className="screener-head">
        <h3>Balcony</h3>
      </div>
      <p className="subtle">
        Experimental analysis — models, portfolios, correlation studies — linked explicitly to the
        stocks and reading that inform them.
      </p>

      <CreateAnalysisForm onCreated={onSelect} />

      {analyses.isPending ? (
        <p className="status">Loading…</p>
      ) : analyses.isError ? (
        <div className="error-banner" role="alert">
          Couldn&apos;t load analyses: {String(analyses.error)}
        </div>
      ) : analyses.data.length === 0 ? (
        <p className="subtle">No analyses yet — start one above.</p>
      ) : (
        <ul className="reference-list">
          {analyses.data.map((a) => (
            <li key={a.id}>
              <button type="button" className="ghost" onClick={() => onSelect(a.id)}>
                <span className="ticker-chip">{a.kind}</span> {a.title}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
