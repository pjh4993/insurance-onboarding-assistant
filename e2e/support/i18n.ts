// UI strings come from the frontend's own catalogs, so a copy change does not break a selector.
import en from "../../frontend/messages/en.json" with { type: "json" };
import ko from "../../frontend/messages/ko.json" with { type: "json" };

export type Locale = "ko" | "en";
const CATALOGS: Record<Locale, unknown> = { en, ko };

/** The message at `key` (dot path) with `{param}` placeholders filled. ICU plurals and selects are not supported. */
export function t(locale: Locale, key: string, params: Record<string, string | number> = {}): string {
  const value = key.split(".").reduce<unknown>((node, part) => (node as Record<string, unknown>)?.[part], CATALOGS[locale]);
  if (typeof value !== "string") throw new Error(`no message ${locale}:${key}`);
  return value.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`));
}
