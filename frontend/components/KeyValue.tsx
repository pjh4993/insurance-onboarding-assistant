"use client";

import { useTranslations } from "next-intl";
import { useFormat } from "@/i18n/useFormat";
import { humanize } from "@/lib/format";

type Fmt = { money: (minor: number, currency: string) => string; yes: string; no: string; none: string };

function renderValue(key: string, value: unknown, currency: string, f: Fmt): React.ReactNode {
  if (value === null || value === undefined || value === "") return <span className="muted">—</span>;
  if (typeof value === "boolean") return value ? f.yes : f.no;
  if (typeof value === "number" && key.endsWith("_minor")) return f.money(value, currency);
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="muted">{f.none}</span>;
    if (value.every((v) => typeof v !== "object" || v === null)) return value.map(String).join(", ");
    return (
      <ul className="kv__list">
        {value.map((v, i) => (
          <li key={i}>{renderValue(key, v, currency, f)}</li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") return <KeyValue data={value as Record<string, unknown>} currency={currency} nested />;
  return String(value);
}

/**
 * Generic, readable rendering of an entity record (keys humanized, *_minor amounts formatted).
 * Keys are backend field names shown as-is to agents; values and placeholders follow the active language.
 */
export function KeyValue({
  data,
  currency,
  nested,
}: {
  data: Record<string, unknown>;
  currency: string;
  nested?: boolean;
}) {
  const t = useTranslations("common");
  const { money } = useFormat();
  const f: Fmt = { money, yes: t("yes"), no: t("no"), none: t("none") };
  const entries = Object.entries(data);
  if (entries.length === 0) return <p className="muted">{t("empty")}</p>;
  return (
    <dl className={`kv ${nested ? "kv--nested" : ""}`}>
      {entries.map(([k, v]) => (
        <div key={k} className="kv__row">
          <dt>{humanize(k.replace(/_minor$/, ""))}</dt>
          <dd>{renderValue(k, v, currency, f)}</dd>
        </div>
      ))}
    </dl>
  );
}
