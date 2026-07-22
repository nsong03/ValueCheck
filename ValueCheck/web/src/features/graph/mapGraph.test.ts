import { describe, expect, it } from "vitest";

import type { GraphOut } from "../../api/client";
import { mapGraph } from "./mapGraph";

const FIXTURE: GraphOut = {
  nodes: [
    { id: "AAPL", label: "Apple Inc.", kind: "company", sector: "Technology" },
    { id: "TSM", label: "TSMC", kind: "company", sector: "Technology" },
    { id: "tag:semis", label: "semis", kind: "tag", sector: null },
  ],
  edges: [
    { source: "TSM", target: "tag:semis", weight: 2 },
    { source: "AAPL", target: "tag:semis", weight: 1 },
  ],
};

describe("mapGraph", () => {
  it("maps nodes with readable names per kind", () => {
    const data = mapGraph(FIXTURE);
    const byId = new Map(data.nodes.map((n) => [n.id, n]));
    expect(byId.get("AAPL")?.name).toBe("AAPL — Apple Inc.");
    expect(byId.get("tag:semis")?.name).toBe("#semis");
    expect(byId.get("AAPL")?.kind).toBe("company");
    expect(byId.get("tag:semis")?.kind).toBe("tag");
  });

  it("sizes nodes by weighted degree", () => {
    const data = mapGraph(FIXTURE);
    const byId = new Map(data.nodes.map((n) => [n.id, n]));
    expect(byId.get("tag:semis")?.val).toBe(4); // 1 + (2+1)
    expect(byId.get("TSM")?.val).toBe(3); // 1 + 2
    expect(byId.get("AAPL")?.val).toBe(2); // 1 + 1
  });

  it("passes edges through as links", () => {
    const data = mapGraph(FIXTURE);
    expect(data.links).toEqual([
      { source: "TSM", target: "tag:semis", weight: 2 },
      { source: "AAPL", target: "tag:semis", weight: 1 },
    ]);
  });
});
