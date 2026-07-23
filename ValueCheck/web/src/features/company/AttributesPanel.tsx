import { useState } from "react";

import { ApiError, type AttributeDefinitionOut, type ValueType } from "../../api/client";
import {
  useAttributeDefinitions,
  useAttributeHistory,
  useCurrentAttributes,
  useSetAttribute,
} from "../../api/hooks";

function ValueEditor({
  definition,
  value,
  onChange,
}: {
  definition: AttributeDefinitionOut | undefined;
  value: string;
  onChange: (v: string) => void;
}) {
  if (definition?.value_type === "scale") {
    return (
      <input
        type="number"
        step="1"
        min={definition.scale_min ?? undefined}
        max={definition.scale_max ?? undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Attribute value"
      />
    );
  }
  if (definition?.value_type === "number") {
    return (
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Attribute value"
      />
    );
  }
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Value"
      aria-label="Attribute value"
      list={definition?.allowed_values ? "attribute-allowed-values" : undefined}
    />
  );
}

function HistoryRow({ ticker, attrKey }: { ticker: string; attrKey: string }) {
  const history = useAttributeHistory(ticker, attrKey);
  if (history.isPending) return <p className="status">Loading history…</p>;
  if (history.isError) return <p className="subtle">Couldn&apos;t load history.</p>;
  return (
    <ul className="attribute-history">
      {history.data.values.map((v) => (
        <li key={v.id}>
          <strong>{v.value}</strong>{" "}
          <span className="subtle">
            {new Date(v.created_at).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}{" "}
            · {v.source}
            {v.reason ? ` — ${v.reason}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Typed, namespaced facts about a company (region, custom sector, quality
 * scores, status) — schema-on-write: the first value for a new key defines
 * its type; existing keys keep their type from then on. Full history is
 * kept per key, so conviction on a dimension can be traced over time. */
export function AttributesPanel({ ticker }: { ticker: string }) {
  const definitions = useAttributeDefinitions();
  const current = useCurrentAttributes(ticker);
  const setAttribute = useSetAttribute(ticker);

  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newValueType, setNewValueType] = useState<ValueType>("text");

  const defByKey = new Map((definitions.data ?? []).map((d) => [d.key, d]));
  const currentEntries = Object.entries(current.data ?? {}).sort(([a], [b]) => a.localeCompare(b));

  const submitExisting = (key: string, value: string) => {
    if (!value.trim()) return;
    setAttribute.mutate({ key, value, source: "grid" });
  };

  return (
    <section data-testid="attributes-panel">
      <div className="notes-head">
        <h3>Attributes</h3>
      </div>
      <p className="subtle">
        Region, sector, quality scores, status — flexible now, curate later.
      </p>

      {current.isPending ? (
        <p className="status">Loading attributes…</p>
      ) : current.isError ? (
        <div className="error-banner" role="alert">
          Couldn&apos;t load attributes: {String(current.error)}
        </div>
      ) : currentEntries.length === 0 ? (
        <p className="subtle">No attributes yet.</p>
      ) : (
        <ul className="attribute-list">
          {currentEntries.map(([key, attr]) => {
            const def = defByKey.get(key);
            return (
              <li key={key} className="attribute-row">
                <span className="attribute-key">{def?.label ?? key}</span>
                <ValueEditorInline
                  definition={def}
                  initialValue={attr.value}
                  onSubmit={(v) => submitExisting(key, v)}
                />
                <button
                  type="button"
                  className="ghost"
                  onClick={() => setExpandedKey(expandedKey === key ? null : key)}
                >
                  {expandedKey === key ? "Hide history" : "History"}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {expandedKey && <HistoryRow ticker={ticker} attrKey={expandedKey} />}

      {setAttribute.isError && (
        <div className="error-banner" role="alert">
          Couldn&apos;t save attribute:{" "}
          {setAttribute.error instanceof ApiError
            ? `${setAttribute.error.message} (${setAttribute.error.code})`
            : String(setAttribute.error)}
        </div>
      )}

      <form
        className="attribute-add-row"
        onSubmit={(e) => {
          e.preventDefault();
          const key = newKey.trim();
          if (!key || !newValue.trim()) return;
          setAttribute.mutate(
            { key, value: newValue.trim(), source: "grid", value_type: newValueType },
            {
              onSuccess: () => {
                setNewKey("");
                setNewValue("");
              },
            },
          );
        }}
      >
        <input
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          placeholder="New attribute (e.g. region, quality.moat)"
          aria-label="New attribute key"
          list="attribute-known-keys"
        />
        <datalist id="attribute-known-keys">
          {(definitions.data ?? []).map((d) => (
            <option key={d.key} value={d.key} />
          ))}
        </datalist>
        <input
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          placeholder="Value"
          aria-label="New attribute value"
        />
        {!defByKey.has(newKey.trim()) && newKey.trim() && (
          <select
            value={newValueType}
            onChange={(e) => setNewValueType(e.target.value as ValueType)}
            aria-label="New attribute type"
          >
            <option value="text">text</option>
            <option value="number">number</option>
            <option value="scale">scale (1-5)</option>
          </select>
        )}
        <button type="submit" disabled={setAttribute.isPending}>
          Set
        </button>
      </form>
    </section>
  );
}

function ValueEditorInline({
  definition,
  initialValue,
  onSubmit,
}: {
  definition: AttributeDefinitionOut | undefined;
  initialValue: string;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState(initialValue);
  return (
    <span className="attribute-value-editor">
      <ValueEditor definition={definition} value={value} onChange={setValue} />
      {value !== initialValue && (
        <button type="button" className="ghost" onClick={() => onSubmit(value)}>
          Save
        </button>
      )}
    </span>
  );
}
