import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { SensitivityOut } from "../../api/client";
import { SensitivityGrid } from "./SensitivityGrid";

afterEach(cleanup);

const FIXTURE: SensitivityOut = {
  wacc_labels: ["WACC 8.7%", "WACC 9.7%", "WACC 10.7%"],
  growth_labels: ["g 2.00%", "g 2.50%", "g 3.00%"],
  grid: [
    [107.88, 114.97, 123.32],
    [93.2, 98.32, 104.2],
    [81.91, 85.74, null],
  ],
};

describe("SensitivityGrid", () => {
  it("renders the grid with WACC rows and growth columns", () => {
    render(<SensitivityGrid data={FIXTURE} />);
    expect(screen.getByText("WACC 9.7%")).toBeTruthy();
    expect(screen.getByText("g 2.50%")).toBeTruthy();
    expect(screen.getByText("114.97")).toBeTruthy();
  });

  it("marks the center cell as the base case", () => {
    render(<SensitivityGrid data={FIXTURE} />);
    const center = screen.getByText("98.32");
    expect(center.className).toContain("center-cell");
  });

  it("renders null cells (invalid terminal value) as em dash", () => {
    render(<SensitivityGrid data={FIXTURE} />);
    expect(screen.getByText("—")).toBeTruthy();
  });
});
