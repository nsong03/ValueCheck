import type { GraphOut } from "../../api/client";

/** Shape react-force-graph-2d consumes. Kept as a pure function so the
 * mapping is testable without a canvas. */
export interface ForceNode {
  id: string;
  name: string;
  kind: "company" | "tag";
  sector: string | null;
  val: number; // node size hint
}

export interface ForceLink {
  source: string;
  target: string;
  weight: number;
}

export interface ForceData {
  nodes: ForceNode[];
  links: ForceLink[];
}

export function mapGraph(data: GraphOut): ForceData {
  const degree = new Map<string, number>();
  for (const e of data.edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + e.weight);
    degree.set(e.target, (degree.get(e.target) ?? 0) + e.weight);
  }
  return {
    nodes: data.nodes.map((n) => ({
      id: n.id,
      name: n.kind === "company" ? `${n.id} — ${n.label}` : `#${n.label}`,
      kind: n.kind === "company" ? "company" : "tag",
      sector: n.sector ?? null,
      val: 1 + (degree.get(n.id) ?? 0),
    })),
    links: data.edges.map((e) => ({ source: e.source, target: e.target, weight: e.weight })),
  };
}
