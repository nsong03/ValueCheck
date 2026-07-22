import type { AssumptionsIn, AssumptionsOut } from "../../api/client";

type LeverKey = keyof AssumptionsIn & keyof AssumptionsOut;

interface Lever {
  key: LeverKey;
  label: string;
  step: number;
  pct: boolean; // display/edit as percent
}

const GROUPS: { title: string; levers: Lever[] }[] = [
  {
    title: "Growth & margins",
    levers: [
      { key: "horizon", label: "Horizon (years)", step: 1, pct: false },
      { key: "rev_growth", label: "Revenue growth (yr 1)", step: 0.1, pct: true },
      { key: "rev_growth_terminal", label: "Revenue growth (final yr)", step: 0.1, pct: true },
      { key: "ebit_margin", label: "EBIT margin", step: 0.1, pct: true },
      { key: "tax_rate", label: "Tax rate", step: 0.1, pct: true },
    ],
  },
  {
    title: "Cash-flow drivers",
    levers: [
      { key: "da_pct_rev", label: "D&A % of revenue", step: 0.1, pct: true },
      { key: "capex_pct_rev", label: "Capex % of revenue", step: 0.1, pct: true },
      { key: "nwc_pct_rev", label: "ΔNWC % of Δrevenue", step: 0.1, pct: true },
    ],
  },
  {
    title: "WACC",
    levers: [
      { key: "risk_free", label: "Risk-free rate", step: 0.1, pct: true },
      { key: "equity_premium", label: "Equity risk premium", step: 0.1, pct: true },
      { key: "beta", label: "Beta", step: 0.05, pct: false },
      { key: "cost_of_debt", label: "Cost of debt", step: 0.1, pct: true },
      { key: "target_debt_weight", label: "Target debt weight", step: 1, pct: true },
    ],
  },
  {
    title: "Terminal value",
    levers: [{ key: "terminal_growth", label: "Terminal growth g", step: 0.05, pct: true }],
  },
];

export function AssumptionsPanel({
  resolved,
  overrides,
  onChange,
  onReset,
  busy,
}: {
  resolved: AssumptionsOut | undefined;
  overrides: AssumptionsIn;
  onChange: (key: keyof AssumptionsIn, value: number | null) => void;
  onReset: () => void;
  busy: boolean;
}) {
  const overrideCount = Object.keys(overrides).length;

  const display = (lever: Lever): string => {
    const raw = overrides[lever.key] ?? resolved?.[lever.key];
    if (raw === undefined || raw === null) return "";
    const value = lever.pct ? raw * 100 : raw;
    return String(Number(value.toFixed(4)));
  };

  const commit = (lever: Lever, text: string) => {
    if (text.trim() === "") {
      onChange(lever.key, null); // cleared -> back to seeded value
      return;
    }
    const parsed = Number(text);
    if (Number.isNaN(parsed)) return;
    onChange(lever.key, lever.pct ? parsed / 100 : parsed);
  };

  return (
    <aside className="assumptions" data-testid="assumptions-panel">
      <div className="assumptions-head">
        <h3>Assumptions {busy && <span className="busy-dot" title="re-valuing…" />}</h3>
        <button type="button" onClick={onReset} disabled={overrideCount === 0}>
          Reset to seeded{overrideCount > 0 ? ` (${overrideCount})` : ""}
        </button>
      </div>
      <p className="subtle">
        Seeded from the company&apos;s own history — every edit re-values immediately.
      </p>
      {GROUPS.map((group) => (
        <fieldset key={group.title}>
          <legend>{group.title}</legend>
          {group.levers.map((lever) => (
            <label key={lever.key} className={overrides[lever.key] !== undefined ? "edited" : ""}>
              <span>
                {lever.label}
                {lever.pct ? " (%)" : ""}
              </span>
              <input
                type="number"
                step={lever.step}
                defaultValue={display(lever)}
                key={`${lever.key}:${display(lever)}`}
                aria-label={lever.label}
                onBlur={(e) => commit(lever, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
              />
            </label>
          ))}
        </fieldset>
      ))}
    </aside>
  );
}
