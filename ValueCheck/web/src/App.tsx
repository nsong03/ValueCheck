import { useState } from "react";

import { CompanyWorkspace } from "./features/company/CompanyWorkspace";
import { GraphView } from "./features/graph/GraphView";
import { SearchPanel } from "./features/search/SearchPanel";

type View = "workspace" | "graph";

export default function App() {
  const [view, setView] = useState<View>("workspace");
  const [ticker, setTicker] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [impacted, setImpacted] = useState<string[] | null>(null);

  const openCompany = (symbol: string) => {
    setTicker(symbol.toUpperCase());
    setView("workspace");
  };

  return (
    <div className="app">
      <header className="topbar">
        <h1>
          ValueCheck <span className="tagline">deterministic DCF, sourced from filings</span>
        </h1>
        <nav className="view-tabs" aria-label="View">
          <button
            type="button"
            className={view === "workspace" ? "tab active" : "tab"}
            onClick={() => setView("workspace")}
          >
            Workspace
          </button>
          <button
            type="button"
            className={view === "graph" ? "tab active" : "tab"}
            onClick={() => setView("graph")}
          >
            Graph
          </button>
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
          <GraphView impacted={impacted} onOpenCompany={openCompany} />
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
