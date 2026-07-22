import type { HistoricalsRow } from "../../api/client";
import { fmtPct } from "../../lib/format";

const fmtCell = (x: number | null | undefined) =>
  x === null || x === undefined ? "—" : x.toLocaleString("en-US", { maximumFractionDigits: 0 });

export function HistoricalsTable({
  rows,
  revenueCagr,
  avgEbitMargin,
}: {
  rows: HistoricalsRow[];
  revenueCagr: number;
  avgEbitMargin: number;
}) {
  return (
    <section>
      <h3>Historicals — from filings ($M)</h3>
      <div className="table-scroll">
        <table className="data-table" data-testid="historicals">
          <thead>
            <tr>
              <th>FY</th>
              <th>Revenue</th>
              <th>EBIT</th>
              <th>EBIT margin</th>
              <th>D&amp;A</th>
              <th>Capex</th>
              <th>NWC</th>
              <th>Tax rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.fiscal_year}>
                <td>{r.fiscal_year}</td>
                <td>{fmtCell(r.revenue)}</td>
                <td>{fmtCell(r.ebit)}</td>
                <td>
                  {r.revenue && r.ebit !== null && r.ebit !== undefined
                    ? fmtPct(r.ebit / r.revenue)
                    : "—"}
                </td>
                <td>{fmtCell(r.da)}</td>
                <td>{fmtCell(r.capex)}</td>
                <td>{fmtCell(r.nwc)}</td>
                <td>{r.tax_rate === null || r.tax_rate === undefined ? "—" : fmtPct(r.tax_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="subtle">
        Revenue CAGR {fmtPct(revenueCagr)} · Avg EBIT margin {fmtPct(avgEbitMargin)}
      </p>
    </section>
  );
}
