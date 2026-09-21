import { formatMoney, humanize } from "@/lib/format";

function renderValue(key: string, value: unknown, currency: string): React.ReactNode {
  if (value === null || value === undefined || value === "") return <span className="muted">—</span>;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number" && key.endsWith("_minor")) return formatMoney(value, currency);
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="muted">none</span>;
    if (value.every((v) => typeof v !== "object" || v === null)) return value.map(String).join(", ");
    return (
      <ul className="kv__list">
        {value.map((v, i) => (
          <li key={i}>{renderValue(key, v, currency)}</li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") return <KeyValue data={value as Record<string, unknown>} currency={currency} nested />;
  return String(value);
}

/** Generic, readable rendering of an entity record (keys humanized, *_minor amounts formatted). */
export function KeyValue({
  data,
  currency,
  nested,
}: {
  data: Record<string, unknown>;
  currency: string;
  nested?: boolean;
}) {
  const entries = Object.entries(data);
  if (entries.length === 0) return <p className="muted">Empty</p>;
  return (
    <dl className={`kv ${nested ? "kv--nested" : ""}`}>
      {entries.map(([k, v]) => (
        <div key={k} className="kv__row">
          <dt>{humanize(k.replace(/_minor$/, ""))}</dt>
          <dd>{renderValue(k, v, currency)}</dd>
        </div>
      ))}
    </dl>
  );
}
