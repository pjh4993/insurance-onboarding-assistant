import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { localeMarket, marketLocale, negotiateLocale, sessionLocale } from "./locales";

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe("message catalogs", () => {
  it("have the same keys in every language", () => {
    expect(keys(ko).sort()).toEqual(keys(en).sort());
  });
});

describe("locale resolution", () => {
  it("defaults a session to its market's language", () => {
    expect(marketLocale("KR")).toBe("ko");
    expect(marketLocale("US")).toBe("en");
  });

  it("defaults a self-serve visitor's market to their language", () => {
    expect(localeMarket("ko")).toBe("KR");
    expect(localeMarket("en")).toBe("US");
  });

  it("uses the session's locale, or the market's when an older backend omits it", () => {
    expect(sessionLocale({ market: "KR", locale: "en" })).toBe("en");
    expect(sessionLocale({ market: "KR" })).toBe("ko");
    expect(sessionLocale({ market: "US", locale: null })).toBe("en");
  });

  it("negotiates Accept-Language by quality, on the primary subtag", () => {
    expect(negotiateLocale("ko-KR,ko;q=0.9,en-US;q=0.8")).toBe("ko");
    expect(negotiateLocale("fr-FR,en;q=0.5,ko;q=0.7")).toBe("ko");
    expect(negotiateLocale("fr-FR,de;q=0.9")).toBe("en");
    expect(negotiateLocale(["en-GB", "ko"])).toBe("en");
    expect(negotiateLocale(null, "ko")).toBe("ko");
  });
});
