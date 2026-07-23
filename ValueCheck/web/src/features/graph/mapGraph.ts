import type { GraphOut } from "../../api/client";

/** Shape react-force-graph-2d consumes. Kept as a pure function so the
 * mapping is testable without a canvas. */
export interface ForceNode {
  id: string;
  name: string;
  kind: "company" | "reference" | "analysis" | "tag";
  sector: string | null;
  collection: string | null;
  val: number; // node size hint
}

export interface ForceLink {
  source: string;
  target: string;
  weight: number;
  kind: "tag" | "link";
}

export interface ForceData {
  nodes: ForceNode[];
  links: ForceLink[];
}

function labelFor(kind: ForceNode["kind"], id: string, label: string): string {
  switch (kind) {
    case "company":
      return `${id} — ${label}`;
    case "tag":
      return `#${label}`;
    default:
      return label;
  }
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
      name: labelFor(n.kind as ForceNode["kind"], n.id, n.label),
      kind: n.kind as ForceNode["kind"],
      sector: n.sector ?? null,
      collection: n.collection ?? null,
      val: 1 + (degree.get(n.id) ?? 0),
    })),
    links: data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      weight: e.weight,
      kind: e.kind as ForceLink["kind"],
    })),
  };
}
