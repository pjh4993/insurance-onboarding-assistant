import type { Locale, Market } from "@/lib/types";

export type { Locale };

// The two languages the app speaks. A session's locale drives the customer UI; the agent picks their own.
export const LOCALES = ["ko", "en"] as const satisfies readonly Locale[];

export const DEFAULT_LOCALE: Locale = "en";

/** Cookie holding the agent console's UI language. Read server-side by i18n/request.ts. */
export const AGENT_LOCALE_COOKIE = "agent_locale";

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

/** The language a market speaks by default (CONTRACTS.md §3: KR → ko, US → en). */
export function marketLocale(market: Market): Locale {
  return market === "KR" ? "ko" : "en";
}

/** The market a visitor starting on the public landing page gets by default: ko → KR, en → US. */
export function localeMarket(locale: Locale): Market {
  return locale === "ko" ? "KR" : "US";
}

/**
 * The first supported language in an Accept-Language header or navigator.languages list,
 * matched on the primary subtag ("ko-KR" → "ko"), else `fallback`.
 */
export function negotiateLocale(preferred: string | readonly string[] | null | undefined, fallback = DEFAULT_LOCALE): Locale {
  if (!preferred) return fallback;
  const tags =
    typeof preferred === "string"
      ? preferred
          .split(",")
          .map((part) => {
            const [tag, ...params] = part.trim().split(";");
            const q = params.find((p) => p.trim().startsWith("q="));
            return { tag, q: q ? Number(q.trim().slice(2)) : 1 };
          })
          .filter((t) => t.tag && !Number.isNaN(t.q) && t.q > 0)
          .sort((a, b) => b.q - a.q)
          .map((t) => t.tag)
      : preferred;
  for (const tag of tags) {
    const primary = tag.toLowerCase().split("-")[0];
    if (isLocale(primary)) return primary;
  }
  return fallback;
}

/** A session's language; older backends omit `locale`, so fall back to the market's. */
export function sessionLocale(session: { market: Market; locale?: Locale | null }): Locale {
  return isLocale(session.locale) ? session.locale : marketLocale(session.market);
}

/** BCP 47 tag for Intl formatting. */
export function intlTag(locale: Locale): string {
  return locale === "ko" ? "ko-KR" : "en-US";
}
