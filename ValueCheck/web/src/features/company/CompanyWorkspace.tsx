import { useState } from "react";

import { useCompany, useValuation } from "../../api/hooks";
import { ApiError, type AssumptionsIn } from "../../api/client";
import { fmtMillions, fmtPrice } from "../../lib/format";
import { NotesSection } from "../notes/NotesSection";
import { AssumptionsPanel } from "./AssumptionsPanel";
import { HistoricalsTable } from "./HistoricalsTable";
import { SensitivityGrid } from "./SensitivityGrid";
import { ValuationResult } from "./ValuationResult";

export function CompanyWorkspace({ ticker }: { ticker: string }) {
  const [overrides, setOverrides] = useState<AssumptionsIn>({});
  const company = useCompany(ticker);
  const valuation = useValuation(ticker, overrides);

  const setLever = (key: keyof AssumptionsIn, value: number | null) => {
    setOverrides((prev) => {
      const next = { ...prev };
      if (value === null) delete next[key];
      else next[key] = value;
      return next;
    });
  };

  if (company.isPending) return <p className="status">Loading {ticker}…</p>;
  if (company.isError) {
    const err = company.error;
    return (
      <div className="error-banner" role="alert">
        <strong>Couldn&apos;t load {ticker}.</strong>{" "}
        {err instanceof ApiError ? `${err.message} (${err.code})` : String(err)}
      </div>
    );
  }

  const fin = company.data;
  return (
    <div className="workspace">
      <section className="company-header">
        <div>
          <h2>
            {fin.name} <span className="ticker-chip">{fin.ticker}</span>
          </h2>
          <p className="subtle">
            {fin.sector} / {fin.industry}
            {fin.sic ? ` · SIC ${fin.sic}` : ""}
          </p>
        </div>
        <dl className="key-stats">
          <div>
            <dt>Price</dt>
            <dd>{fmtPrice(fin.price)}</dd>
          </div>
          <div>
            <dt>Market cap</dt>
            <dd>{fmtMillions(fin.market_cap)}</dd>
          </div>
          <div>
            <dt>Net debt</dt>
            <dd>{fmtMillions(fin.net_debt)}</dd>
          </div>
          <div>
            <dt>Beta</dt>
            <dd>{fin.beta.toFixed(2)}</dd>
          </div>
        </dl>
      </section>

      <HistoricalsTable
        rows={fin.historicals}
        revenueCagr={fin.revenue_cagr}
        avgEbitMargin={fin.avg_ebit_margin}
      />

      <div className="valuation-layout">
        <AssumptionsPanel
          resolved={valuation.data?.assumptions}
          overrides={overrides}
          onChange={setLever}
          onReset={() => setOverrides({})}
          busy={valuation.isFetching}
        />
        <div className="valuation-outputs">
          {valuation.isError ? (
            <div className="error-banner" role="alert">
              <strong>Valuation failed.</strong>{" "}
              {valuation.error instanceof ApiError
                ? `${valuation.error.message} (${valuation.error.code})`
                : String(valuation.error)}
            </div>
          ) : valuation.data ? (
            <>
              <ValuationResult data={valuation.data} stale={valuation.isFetching} />
              <SensitivityGrid data={valuation.data.sensitivity} />
            </>
          ) : (
            <p className="status">Running valuation…</p>
          )}
        </div>
      </div>

      <NotesSection ticker={ticker} />
    </div>
  );
}
