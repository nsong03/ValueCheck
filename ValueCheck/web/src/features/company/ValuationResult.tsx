import type { ValuationResponse } from "../../api/client";
import { fmtMillions, fmtPct, fmtPrice, fmtSignedPct } from "../../lib/format";

export function ValuationResult({ data, stale }: { data: ValuationResponse; stale: boolean }) {
  const upsideClass =
    data.upside === null || data.upside === undefined
      ? ""
      : data.upside >= 0
        ? "gain"
        : "loss";

  return (
    <section className={stale ? "result stale" : "result"} data-testid="valuation-result">
      <h3>Valuation</h3>
      <div className="headline">
        <div className="fair-value">
          <span className="big">{fmtPrice(data.fair_value_per_share)}</span>
          <span className="subtle">fair value / share</span>
        </div>
        <div className={`upside ${upsideClass}`}>
          <span className="big">{fmtSignedPct(data.upside)}</span>
          <span className="subtle">vs current price</span>
        </div>
      </div>
      <dl className="result-grid">
        <div>
          <dt>WACC</dt>
          <dd>{fmtPct(data.wacc, 2)}</dd>
        </div>
        <div>
          <dt>Enterprise value</dt>
          <dd>{fmtMillions(data.enterprise_value)}</dd>
        </div>
        <div>
          <dt>Equity value</dt>
          <dd>{fmtMillions(data.equity_value)}</dd>
        </div>
        <div>
          <dt>Run</dt>
          <dd>#{data.valuation_id}</dd>
        </div>
      </dl>

      {data.warnings.length > 0 && (
        <ul className="warnings" data-testid="warnings">
          {data.warnings.map((w) => (
            <li key={w}>⚠ {w}</li>
          ))}
        </ul>
      )}

      <details>
        <summary>Projection (FCFF, $M)</summary>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Yr</th>
                <th>Revenue</th>
                <th>Growth</th>
                <th>EBIT</th>
                <th>NOPAT</th>
                <th>D&amp;A</th>
                <th>Capex</th>
                <th>ΔNWC</th>
                <th>FCFF</th>
                <th>PV(FCFF)</th>
              </tr>
            </thead>
            <tbody>
              {data.projection.map((r) => (
                <tr key={r.year}>
                  <td>{r.year}</td>
                  <td>{r.revenue.toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                  <td>{fmtPct(r.growth)}</td>
                  <td>{r.ebit.toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                  <td>{r.nopat.toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                  <td>{r.da.toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                  <td>{r.capex.toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                  <td>{r.d_nwc.toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                  <td>{r.fcff.toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                  <td>{r.pv_fcff.toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <details>
        <summary>Sources ({data.sources.length})</summary>
        <ul className="sources">
          {data.sources.map((s) => (
            <li key={`${s.accession}-${s.label}`}>
              {s.url && s.url.startsWith("http") ? (
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.label}
                </a>
              ) : (
                <span>{s.label}</span>
              )}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
