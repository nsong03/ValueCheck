import { useState } from "react";

import { BalconyView } from "./features/balcony/BalconyView";
import { CompanyWorkspace } from "./features/company/CompanyWorkspace";
import { GraphView } from "./features/graph/GraphView";
import { LibraryView } from "./features/library/LibraryView";
import { ScreenerView } from "./features/screener/ScreenerView";
import { SearchPanel } from "./features/search/SearchPanel";

type View = "workspace" | "screener" | "library" | "balcony" | "graph";

export default function App() {
  const [view, setView] = useState<View>("workspace");
  const [ticker, setTicker] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [impacted, setImpacted] = useState<string[] | null>(null);
  const [libraryId, setLibraryId] = useState<number | null>(null);
  const [analysisId, setAnalysisId] = useState<number | null>(null);

  const openCompany = (symbol: string) => {
    setTicker(symbol.toUpperCase());
    setView("workspace");
  };
  const openReference = (id: number) => {
    setLibraryId(id);
    setView("library");
  };
  const openAnalysis = (id: number) => {
    setAnalysisId(id);
    setView("balcony");
  };

  return (
    <div className="app">
      <header className="topbar">
        <h1>
          ValueCheck <span className="tagline">deterministic DCF, sourced from filings</span>
        </h1>
        <nav className="view-tabs" aria-label="View">
          {(
            [
              ["workspace", "Workspace"],
              ["screener", "Screener"],
              ["library", "Library"],
              ["balcony", "Balcony"],
              ["graph", "Graph"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={view === key ? "tab active" : "tab"}
              onClick={() => setView(key)}
            >
              {label}
            </button>
          ))}
        </nav>
        <form
          className="ticker-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) openCompany(draft.trim());
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ticker (e.g. DEMO, AAPL)"
            aria-label="Ticker"
          />
          <button type="submit">Load</button>
        </form>
      </header>

      <SearchPanel
        onOpenCompany={openCompany}
        onImpacted={(tickers) => {
          setImpacted(tickers);
          setView("graph");
        }}
      />

      <main>
        {view === "graph" ? (
          <GraphView
            impacted={impacted}
            onOpenCompany={openCompany}
            onOpenReference={openReference}
            onOpenAnalysis={openAnalysis}
          />
        ) : view === "screener" ? (
          <ScreenerView onOpenCompany={openCompany} />
        ) : view === "library" ? (
          <LibraryView selected={libraryId} onSelect={setLibraryId} />
        ) : view === "balcony" ? (
          <BalconyView selected={analysisId} onSelect={setAnalysisId} />
        ) : ticker === null ? (
          <p className="empty-state">
            Enter a ticker to load filings and run a valuation. Try <code>DEMO</code> for the
            offline demo company.
          </p>
        ) : (
          <CompanyWorkspace ticker={ticker} />
        )}
      </main>
    </div>
  );
}
