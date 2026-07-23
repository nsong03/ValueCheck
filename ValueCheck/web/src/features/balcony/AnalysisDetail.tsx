import { useState } from "react";

import { ApiError } from "../../api/client";
import {
  useAddAnalysisCompany,
  useAddAnalysisLink,
  useAddAnalysisReference,
  useAnalyses,
  useAnalysis,
  useAnalysisCompanies,
  useAnalysisLinks,
  useAnalysisReferences,
  useDeleteAnalysis,
  useReferences,
  useRemoveAnalysisCompany,
  useRemoveAnalysisLink,
  useRemoveAnalysisReference,
  useUpdateAnalysis,
} from "../../api/hooks";
import { NotesSection } from "../notes/NotesSection";

function CompanyLinks({ analysisId }: { analysisId: number }) {
  const companies = useAnalysisCompanies(analysisId);
  const add = useAddAnalysisCompany(analysisId);
  const remove = useRemoveAnalysisCompany(analysisId);
  const [ticker, setTicker] = useState("");

  return (
    <div className="constituent-block">
      <h4>Companies</h4>
      <div className="tag-chips">
        {(companies.data?.tickers ?? []).map((t) => (
          <span key={t} className="tag-chip">
            {t}
            <button type="button" aria-label={`Remove ${t}`} onClick={() => remove.mutate(t)}>
              ×
            </button>
          </span>
        ))}
      </div>
      <form
        className="link-add-row"
        onSubmit={(e) => {
          e.preventDefault();
          const t = ticker.trim();
          if (!t) return;
          add.mutate(t, { onSuccess: () => setTicker("") });
        }}
      >
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Ticker (e.g. AAPL)"
          aria-label="Add company ticker"
        />
        <button type="submit">Add</button>
      </form>
    </div>
  );
}

function ReferenceLinks({ analysisId }: { analysisId: number }) {
  const references = useAnalysisReferences(analysisId);
  const allReferences = useReferences();
  const add = useAddAnalysisReference(analysisId);
  const remove = useRemoveAnalysisReference(analysisId);
  const [pick, setPick] = useState("");

  const byId = new Map((allReferences.data ?? []).map((r) => [r.id, r]));
  const linkedIds = new Set(references.data?.reference_ids ?? []);
  const available = (allReferences.data ?? []).filter((r) => !linkedIds.has(r.id));

  return (
    <div className="constituent-block">
      <h4>References</h4>
      <ul className="reference-list">
        {(references.data?.reference_ids ?? []).map((id) => (
          <li key={id}>
            {byId.get(id)?.title ?? `#${id}`}{" "}
            <button type="button" className="ghost danger" onClick={() => remove.mutate(id)}>
              Remove
            </button>
          </li>
        ))}
      </ul>
      <form
        className="link-add-row"
        onSubmit={(e) => {
          e.preventDefault();
          const id = Number(pick);
          if (!id) return;
          add.mutate(id, { onSuccess: () => setPick("") });
        }}
      >
        <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Pick a reference">
          <option value="">Pick a reference…</option>
          {available.map((r) => (
            <option key={r.id} value={r.id}>
              {r.title}
            </option>
          ))}
        </select>
        <button type="submit" disabled={!pick}>
          Add
        </button>
      </form>
    </div>
  );
}

function AnalysisLinks({ analysisId }: { analysisId: number }) {
  const links = useAnalysisLinks(analysisId);
  const allAnalyses = useAnalyses();
  const add = useAddAnalysisLink(analysisId);
  const remove = useRemoveAnalysisLink(analysisId);
  const [pick, setPick] = useState("");

  const byId = new Map((allAnalyses.data ?? []).map((a) => [a.id, a]));
  const linkedIds = new Set(links.data?.analysis_ids ?? []);
  const available = (allAnalyses.data ?? []).filter(
    (a) => a.id !== analysisId && !linkedIds.has(a.id),
  );

  return (
    <div className="constituent-block">
      <h4>Related analyses</h4>
      <ul className="reference-list">
        {(links.data?.analysis_ids ?? []).map((id) => (
          <li key={id}>
            {byId.get(id)?.title ?? `#${id}`}{" "}
            <button type="button" className="ghost danger" onClick={() => remove.mutate(id)}>
              Remove
            </button>
          </li>
        ))}
      </ul>
      <form
        className="link-add-row"
        onSubmit={(e) => {
          e.preventDefault();
          const id = Number(pick);
          if (!id) return;
          add.mutate(id, { onSuccess: () => setPick("") });
        }}
      >
        <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Pick an analysis">
          <option value="">Pick an analysis…</option>
          {available.map((a) => (
            <option key={a.id} value={a.id}>
              {a.title}
            </option>
          ))}
        </select>
        <button type="submit" disabled={!pick}>
          Add
        </button>
      </form>
    </div>
  );
}

/** One analysis: editable metadata, explicit links to its constituent
 * companies/references/other analyses, and its own notes. */
export function AnalysisDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const analysis = useAnalysis(id);
  const update = useUpdateAnalysis();
  const remove = useDeleteAnalysis();
  const [editingTitle, setEditingTitle] = useState(false);
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [editingSummary, setEditingSummary] = useState(false);

  if (analysis.isPending) return <p className="status">Loading…</p>;
  if (analysis.isError) {
    return (
      <div className="error-banner" role="alert">
        Couldn&apos;t load analysis: {String(analysis.error)}
      </div>
    );
  }
  const a = analysis.data;

  return (
    <div className="workspace">
      <button type="button" className="ghost" onClick={onBack}>
        ← Back to balcony
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
                if (title.trim() && title !== a.title) {
                  update.mutate({ id: a.id, patch: { title: title.trim() } });
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
              aria-label="Analysis title"
            />
          ) : (
            <h2
              onClick={() => {
                setTitle(a.title);
                setEditingTitle(true);
              }}
            >
              {a.title} <span className="ticker-chip">{a.kind}</span>
            </h2>
          )}
          {editingSummary ? (
            <textarea
              autoFocus
              className="subtle"
              value={summary}
              rows={2}
              onChange={(e) => setSummary(e.target.value)}
              onBlur={() => {
                setEditingSummary(false);
                if (summary !== a.summary) update.mutate({ id: a.id, patch: { summary } });
              }}
              aria-label="Analysis summary"
            />
          ) : (
            <p
              className="subtle"
              onClick={() => {
                setSummary(a.summary);
                setEditingSummary(true);
              }}
            >
              {a.summary || "Click to add a summary…"}
            </p>
          )}
        </div>
        <button
          type="button"
          className="ghost danger"
          onClick={() => {
            if (confirm(`Delete "${a.title}"? This also deletes its notes and links.`)) {
              remove.mutate(a.id, { onSuccess: onBack });
            }
          }}
        >
          Delete
        </button>
      </section>

      {update.isError && (
        <div className="error-banner" role="alert">
          {update.error instanceof ApiError
            ? `${update.error.message} (${update.error.code})`
            : String(update.error)}
        </div>
      )}

      <div className="valuation-layout">
        <CompanyLinks analysisId={a.id} />
        <div className="valuation-outputs">
          <ReferenceLinks analysisId={a.id} />
          <AnalysisLinks analysisId={a.id} />
        </div>
      </div>

      <NotesSection subject={{ kind: "analysis", id: a.id }} />
    </div>
  );
}
