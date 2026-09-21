/** Number of minor-unit digits ISO 4217 assigns to a currency (KRW 0, USD 2, ...). */
export function currencyDigits(currency: string): number {
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).resolvedOptions()
      .maximumFractionDigits ?? 2;
  } catch {
    return 2;
  }
}

/** Format integer minor units + ISO 4217 currency, e.g. (490000, "KRW") -> "₩490,000", (1299, "USD") -> "$12.99". */
export function formatMoney(minor: number, currency: string, locale = "en-US"): string {
  const digits = currencyDigits(currency);
  const major = minor / 10 ** digits;
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(major);
  } catch {
    return `${major.toFixed(digits)} ${currency}`;
  }
}

const ACRONYMS = new Set(["otp", "id", "imei", "kr", "us"]);

/** "PROTECT_DEVICE" -> "Protect device", "OTP" -> "OTP" */
export function humanize(value: string): string {
  const s = value
    .replace(/_/g, " ")
    .toLowerCase()
    .split(" ")
    .map((w) => (ACRONYMS.has(w) ? w.toUpperCase() : w))
    .join(" ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatDate(iso: string, locale = "en-US"): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric" });
}

export function formatTime(iso: string, locale = "en-US"): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
}

export type AgoUnit = "seconds" | "minutes" | "hours" | "days";

/** How long ago, as a unit and a count for a translated "3m ago" message; `now` is injectable for tests. */
export function agoParts(iso: string, now: number = Date.now()): { unit: AgoUnit; n: number } | null {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return { unit: "seconds", n: s };
  const m = Math.round(s / 60);
  if (m < 60) return { unit: "minutes", n: m };
  const h = Math.round(m / 60);
  if (h < 48) return { unit: "hours", n: h };
  return { unit: "days", n: Math.round(h / 24) };
}
