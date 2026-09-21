import type { BillingPeriod } from "./types";

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

const PERIOD_LABEL: Record<BillingPeriod, string> = {
  MONTHLY: "per month",
  ONE_TIME: "one-time",
  PER_TRIP: "per trip",
};

export function formatBillingPeriod(period: BillingPeriod | string): string {
  return PERIOD_LABEL[period as BillingPeriod] ?? period.toLowerCase().replace(/_/g, " ");
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

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

/** "3m ago" style; `now` is injectable for tests. */
export function formatAgo(iso: string, now: number = Date.now()): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}
