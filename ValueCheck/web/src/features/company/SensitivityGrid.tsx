import type { SensitivityOut } from "../../api/client";

/** Fair value/share over WACC (rows) x terminal growth (cols) — the range
 * and its drivers, not one number. Center cell = the base case. */
export function SensitivityGrid({ data }: { data: SensitivityOut }) {
  const centerRow = Math.floor(data.wacc_labels.length / 2);
  const centerCol = Math.floor(data.growth_labels.length / 2);

  return (
    <section data-testid="sensitivity">
      <h3>Sensitivity — fair value / share</h3>
      <div className="table-scroll">
        <table className="data-table sensitivity">
          <thead>
            <tr>
              <th />
              {data.growth_labels.map((g) => (
                <th key={g}>{g}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.grid.map((row, i) => (
              <tr key={data.wacc_labels[i]}>
                <th>{data.wacc_labels[i]}</th>
                {row.map((v, j) => (
                  <td
                    key={`${i}-${j}`}
                    className={i === centerRow && j === centerCol ? "center-cell" : ""}
                  >
                    {v === null || v === undefined ? "—" : v.toFixed(2)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
