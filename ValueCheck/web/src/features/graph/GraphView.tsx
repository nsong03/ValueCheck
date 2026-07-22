import { useMemo, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

import { useGraph } from "../../api/hooks";
import { mapGraph, type ForceNode } from "./mapGraph";

/** Basic force-directed render of the research graph. Deliberately minimal —
 * the exact visualization is a deferred product decision (BUILD_SPEC Phase 8);
 * this proves the data layer end to end. */
export function GraphView({
  impacted,
  onOpenCompany,
}: {
  impacted: string[] | null;
  onOpenCompany: (ticker: string) => void;
}) {
  const [sector, setSector] = useState("");
  const [useImpacted, setUseImpacted] = useState(impacted !== null);

  const filters = useMemo(
    () => ({
      ...(sector.trim() ? { sector: sector.trim() } : {}),
      ...(useImpacted && impacted && impacted.length > 0 ? { tickers: impacted } : {}),
    }),
    [sector, useImpacted, impacted],
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
            nodeColor={(node) => ((node as ForceNode).kind === "company" ? "#1d4ed8" : "#f59e0b")}
            linkWidth={(link) => Math.min(4, (link as { weight?: number }).weight ?? 1)}
            linkColor={() => "#cbd5e1"}
            onNodeClick={(node) => {
              const n = node as ForceNode;
              if (n.kind === "company") onOpenCompany(n.id);
            }}
          />
          <p className="subtle">
            <span className="legend-dot company" /> company · <span className="legend-dot tag" />{" "}
            tag — click a company to open its workspace
          </p>
        </div>
      )}
    </section>
  );
}
