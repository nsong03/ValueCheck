import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";

import type { AttributeDefinitionOut, ScreenerRowOut } from "../../api/client";
import { useScreenerColumns, useScreenerRows, useSetAttribute } from "../../api/hooks";
import { fmtMillions, fmtPrice } from "../../lib/format";

function AttributeCell({
  ticker,
  def,
  value,
}: {
  ticker: string;
  def: AttributeDefinitionOut;
  value: string | undefined;
}) {
  const setAttribute = useSetAttribute(ticker);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");

  if (!editing) {
    return (
      <button type="button" className="screener-cell-edit" onClick={() => setEditing(true)}>
        {value ?? <span className="subtle">—</span>}
      </button>
    );
  }
  return (
    <input
      autoFocus
      className="screener-cell-input"
      defaultValue={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        setEditing(false);
        if (draft.trim() && draft !== value) {
          setAttribute.mutate({ key: def.key, value: draft.trim(), source: "grid" });
        }
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") setEditing(false);
      }}
    />
  );
}

/** Spreadsheet-style view over every tracked company: financials, latest
 * valuation, tags, and current research attributes as dynamic columns —
 * click a cell to edit an attribute directly (no note required). */
export function ScreenerView({ onOpenCompany }: { onOpenCompany: (ticker: string) => void }) {
  const rows = useScreenerRows();
  const columns = useScreenerColumns();
  const [sorting, setSorting] = useState<SortingState>([]);
  const [filter, setFilter] = useState("");

  const attributeDefs = columns.data?.columns ?? [];

  const columnDefs = useMemo<ColumnDef<ScreenerRowOut>[]>(() => {
    const core: ColumnDef<ScreenerRowOut>[] = [
      {
        id: "ticker",
        header: "Ticker",
        accessorKey: "ticker",
        cell: ({ row }) => (
          <button type="button" className="ticker-pill" onClick={() => onOpenCompany(row.original.ticker)}>
            {row.original.ticker}
          </button>
        ),
      },
      { id: "name", header: "Name", accessorKey: "name" },
      { id: "sector", header: "Sector", accessorKey: "sector" },
      { id: "industry", header: "Industry", accessorKey: "industry" },
      {
        id: "price",
        header: "Price",
        accessorKey: "price",
        cell: ({ getValue }) => fmtPrice(getValue<number>()),
      },
      {
        id: "market_cap",
        header: "Market cap",
        accessorKey: "market_cap",
        cell: ({ getValue }) => fmtMillions(getValue<number>()),
      },
      {
        id: "fair_value",
        header: "Fair value",
        accessorFn: (r) => r.latest_valuation?.fair_value_per_share ?? null,
        cell: ({ getValue }) => {
          const v = getValue<number | null>();
          return v === null ? <span className="subtle">—</span> : fmtPrice(v);
        },
      },
      {
        id: "upside",
        header: "Upside",
        accessorFn: (r) => r.latest_valuation?.upside ?? null,
        cell: ({ getValue }) => {
          const v = getValue<number | null>();
          if (v === null) return <span className="subtle">—</span>;
          return (
            <span className={v >= 0 ? "positive" : "negative"}>{(v * 100).toFixed(1)}%</span>
          );
        },
      },
      {
        id: "revenue_cagr",
        header: "Rev. CAGR",
        accessorKey: "revenue_cagr",
        cell: ({ getValue }) => `${(getValue<number>() * 100).toFixed(1)}%`,
      },
      {
        id: "tags",
        header: "Tags",
        accessorFn: (r) => r.tags.join(", "),
        cell: ({ row }) => (
          <span className="screener-tags">
            {row.original.tags.map((t) => (
              <span key={t} className="tag-chip readonly">
                {t}
              </span>
            ))}
          </span>
        ),
      },
      {
        id: "note_count",
        header: "Notes",
        accessorKey: "note_count",
      },
    ];

    const attributeColumns: ColumnDef<ScreenerRowOut>[] = attributeDefs.map((def) => ({
      id: `attr:${def.key}`,
      header: def.label,
      accessorFn: (r) => r.attributes[def.key]?.value ?? "",
      cell: ({ row }) => (
        <AttributeCell
          ticker={row.original.ticker}
          def={def}
          value={row.original.attributes[def.key]?.value}
        />
      ),
    }));

    return [...core, ...attributeColumns];
  }, [attributeDefs, onOpenCompany]);

  const filteredRows = useMemo(() => {
    const all = rows.data?.rows ?? [];
    const q = filter.trim().toLowerCase();
    if (!q) return all;
    return all.filter(
      (r) =>
        r.ticker.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        r.sector.toLowerCase().includes(q) ||
        r.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }, [rows.data, filter]);

  const table = useReactTable({
    data: filteredRows,
    columns: columnDefs,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <section data-testid="screener-view">
      <div className="screener-head">
        <h3>Screener</h3>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by ticker, name, sector, tag…"
          aria-label="Filter screener"
        />
      </div>

      {rows.isError && (
        <div className="error-banner" role="alert">
          Couldn&apos;t load screener: {String(rows.error)}
        </div>
      )}
      {rows.isPending ? (
        <p className="status">Loading screener…</p>
      ) : filteredRows.length === 0 ? (
        <p className="subtle">No companies tracked yet — load one from the Workspace tab first.</p>
      ) : (
        <div className="screener-table-wrap">
          <table className="screener-table">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => (
                    <th key={h.id} onClick={h.column.getToggleSortingHandler()}>
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {{ asc: " ▲", desc: " ▼" }[h.column.getIsSorted() as string] ?? ""}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
