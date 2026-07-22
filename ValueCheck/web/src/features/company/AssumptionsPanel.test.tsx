import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AssumptionsOut } from "../../api/client";
import { AssumptionsPanel } from "./AssumptionsPanel";

afterEach(cleanup);

const RESOLVED: AssumptionsOut = {
  horizon: 5,
  rev_growth: 0.1017,
  rev_growth_terminal: 0.03,
  ebit_margin: 0.2772,
  tax_rate: 0.149,
  da_pct_rev: 0.0355,
  capex_pct_rev: 0.0306,
  nwc_pct_rev: 0.01,
  risk_free: 0.043,
  equity_premium: 0.05,
  beta: 1.28,
  cost_of_debt: 0.045,
  target_debt_weight: 0.15,
  terminal_growth: 0.025,
};

describe("AssumptionsPanel", () => {
  it("shows seeded values as percentages", () => {
    render(
      <AssumptionsPanel
        resolved={RESOLVED}
        overrides={{}}
        onChange={() => {}}
        onReset={() => {}}
        busy={false}
      />,
    );
    const margin = screen.getByLabelText("EBIT margin") as HTMLInputElement;
    expect(margin.value).toBe("27.72"); // 0.2772 -> 27.72%
    const beta = screen.getByLabelText("Beta") as HTMLInputElement;
    expect(beta.value).toBe("1.28"); // not a percent field
  });

  it("editing a lever commits the fraction value on blur (re-values)", () => {
    const onChange = vi.fn();
    render(
      <AssumptionsPanel
        resolved={RESOLVED}
        overrides={{}}
        onChange={onChange}
        onReset={() => {}}
        busy={false}
      />,
    );
    const margin = screen.getByLabelText("EBIT margin") as HTMLInputElement;
    fireEvent.change(margin, { target: { value: "29" } });
    fireEvent.blur(margin);
    expect(onChange).toHaveBeenCalledWith("ebit_margin", 0.29);
  });

  it("clearing a lever reverts to seeded (null override)", () => {
    const onChange = vi.fn();
    render(
      <AssumptionsPanel
        resolved={RESOLVED}
        overrides={{ ebit_margin: 0.29 }}
        onChange={onChange}
        onReset={() => {}}
        busy={false}
      />,
    );
    const margin = screen.getByLabelText("EBIT margin") as HTMLInputElement;
    fireEvent.change(margin, { target: { value: "" } });
    fireEvent.blur(margin);
    expect(onChange).toHaveBeenCalledWith("ebit_margin", null);
  });

  it("reset button reflects override count", () => {
    const onReset = vi.fn();
    render(
      <AssumptionsPanel
        resolved={RESOLVED}
        overrides={{ ebit_margin: 0.29, beta: 1.1 }}
        onChange={() => {}}
        onReset={onReset}
        busy={false}
      />,
    );
    const btn = screen.getByRole("button", { name: /Reset to seeded \(2\)/ });
    fireEvent.click(btn);
    expect(onReset).toHaveBeenCalledOnce();
  });
});
