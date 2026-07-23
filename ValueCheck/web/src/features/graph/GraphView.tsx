import { useMemo, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

import { useGraph } from "../../api/hooks";
import { mapGraph, type ForceLink, type ForceNode } from "./mapGraph";

const NODE_COLOR: Record<ForceNode["kind"], string> = {
  company: "#1d4ed8",
  reference: "#d97706",
  analysis: "#7c3aed",
  tag: "#94a3b8",
};

/** Basic force-directed render of the research graph. Deliberately minimal —
 * the exact visualization is a deferred product decision; this proves the
 * data layer end to end for all four node kinds. */
export function GraphView({
  impacted,
  onOpenCompany,
  onOpenReference,
  onOpenAnalysis,
}: {
  impacted: string[] | null;
  onOpenCompany: (ticker: string) => void;
  onOpenReference: (id: number) => void;
  onOpenAnalysis: (id: number) => void;
}) {
  const [sector, setSector] = useState("");
  const [collection, setCollection] = useState("");
  const [useImpacted, setUseImpacted] = useState(impacted !== null);

  const filters = useMemo(
    () => ({
      ...(sector.trim() ? { sector: sector.trim() } : {}),
      ...(collection.trim() ? { collection: collection.trim() } : {}),
      ...(useImpacted && impacted && impacted.length > 0 ? { tickers: impacted } : {}),
    }),
    [sector, collection, useImpacted, impacted],
  );
  const graph = useGraph(filters);
  const data = useMemo(() => (graph.data ? mapGraph(graph.data) : null), [graph.data]);

  return (
    <section data-testid="graph-view">
      <div className="graph-controls">
        <h3>Research graph</h3>
        <input
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          placeholder="Filter by sector (exact)"
          aria-label="Sector filter"
        />
        <input
          value={collection}
          onChange={(e) => setCollection(e.target.value)}
          placeholder="Filter by collection (exact)"
          aria-label="Collection filter"
        />
        {impacted !== null && (
          <label className="graph-toggle">
            <input
              type="checkbox"
              checked={useImpacted}
              onChange={(e) => setUseImpacted(e.target.checked)}
            />
            only search-impacted ({impacted.length})
          </label>
        )}
      </div>

      {graph.isError && (
        <div className="error-banner" role="alert">
          Couldn&apos;t load graph: {String(graph.error)}
        </div>
      )}
      {data === null ? (
        <p className="status">Loading graph…</p>
      ) : data.nodes.length === 0 ? (
        <p className="subtle">Nothing to show — load companies and write tagged notes first.</p>
      ) : (
        <div className="graph-canvas">
          <ForceGraph2D
            graphData={data}
            width={820}
            height={520}
            nodeLabel="name"
            nodeVal="val"
            nodeColor={(node) => NODE_COLOR[(node as ForceNode).kind]}
            linkWidth={(link) => {
              const l = link as ForceLink;
              return l.kind === "link" ? 3 : Math.min(4, l.weight);
            }}
            linkColor={(link) => ((link as ForceLink).kind === "link" ? "#7c3aed" : "#cbd5e1")}
            linkLineDash={(link) => ((link as ForceLink).kind === "tag" ? [2, 2] : [])}
            onNodeClick={(node) => {
              const n = node as ForceNode;
              if (n.kind === "company") onOpenCompany(n.id);
              else if (n.kind === "reference") onOpenReference(Number(n.id.split(":")[1]));
              else if (n.kind === "analysis") onOpenAnalysis(Number(n.id.split(":")[1]));
            }}
          />
          <p className="subtle">
            <span className="legend-dot company" /> company · <span className="legend-dot reference" />{" "}
            reference · <span className="legend-dot analysis" /> analysis ·{" "}
            <span className="legend-dot tag" /> tag — dashed = shared tag, solid purple = explicit
            link — click a node to open it
          </p>
        </div>
      )}
    </section>
  );
}
