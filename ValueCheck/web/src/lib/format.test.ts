import { describe, expect, it } from "vitest";

import { fmtMillions, fmtPct, fmtPrice, fmtSignedPct } from "./format";

describe("fmtMillions", () => {
  it("scales $M inputs to B/T", () => {
    expect(fmtMillions(950)).toBe("$950M");
    expect(fmtMillions(1_578_350)).toBe("$1.58T");
    expect(fmtMillions(49_533)).toBe("$49.5B");
  });
  it("handles null/NaN as em dash", () => {
    expect(fmtMillions(null)).toBe("—");
    expect(fmtMillions(Number.NaN)).toBe("—");
  });
});

describe("fmtPct / fmtSignedPct", () => {
  it("formats fractions as percentages", () => {
    expect(fmtPct(0.0967, 2)).toBe("9.67%");
    expect(fmtSignedPct(0.12)).toBe("+12.0%");
    expect(fmtSignedPct(-0.496)).toBe("-49.6%");
  });
  it("handles null", () => {
    expect(fmtPct(null)).toBe("—");
  });
});

describe("fmtPrice", () => {
  it("formats per-share prices", () => {
    expect(fmtPrice(98.31624)).toBe("$98.32");
    expect(fmtPrice(null)).toBe("—");
  });
});
