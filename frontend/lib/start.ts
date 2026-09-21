// Pure helpers for the public start flow: / → POST /api/start → backend POST /api/public/sessions (unit-tested).
import { isLocale } from "@/i18n/locales";
import type { Locale, Market } from "./types";

export type StartBody = { market: Market; locale: Locale | null };

/** The browser's body for POST /api/start, or null if it is not one; only these two fields go upstream. */
export function parseStartBody(body: unknown): StartBody | null {
  if (!body || typeof body !== "object") return null;
  const { market, locale } = body as Record<string, unknown>;
  if (market !== "KR" && market !== "US") return null;
  if (locale !== undefined && locale !== null && !isLocale(locale)) return null;
  return { market, locale: isLocale(locale) ? locale : null };
}

/**
 * The client's address for the backend's per-IP limit: the first entry of X-Forwarded-For, which the ALB
 * sets to the connecting address (plus anything the client sent before it). Null when there is none.
 */
export function clientIp(forwardedFor: string | null | undefined): string | null {
  const first = forwardedFor?.split(",")[0]?.trim();
  return first && first.length <= 64 ? first : null;
}

/** Seconds to wait after a 429: the body's retry_after, else the Retry-After header (seconds form). */
export function retryAfterSeconds(bodyValue: unknown, header: string | null | undefined): number | null {
  for (const v of [bodyValue, header]) {
    const n = typeof v === "number" ? v : typeof v === "string" && v.trim() !== "" ? Number(v) : NaN;
    if (Number.isFinite(n) && n >= 0) return Math.ceil(n);
  }
  return null;
}

/** Whole minutes to show in the "try again in N minutes" message (at least 1), or null when unknown. */
export function retryMinutes(seconds: number | null | undefined): number | null {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return null;
  return Math.max(1, Math.ceil(seconds / 60));
}
