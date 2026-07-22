import { useState } from "react";

import { CompanyWorkspace } from "./features/company/CompanyWorkspace";

export default function App() {
  const [ticker, setTicker] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const load = () => {
    const symbol = draft.trim().toUpperCase();
    if (symbol) setTicker(symbol);
  };

  return (
    <div className="app">
      <header className="topbar">
        <h1>
          ValueCheck <span className="tagline">deterministic DCF, sourced from filings</span>
        </h1>
        <form
          className="ticker-form"
          onSubmit={(e) => {
            e.preventDefault();
            load();
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
      <main>
        {ticker === null ? (
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
