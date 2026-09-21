import { describe, expect, it } from "vitest";
import { clientIp, parseStartBody, retryAfterSeconds, retryMinutes } from "./start";

describe("parseStartBody", () => {
  it("keeps a market and a known locale", () => {
    expect(parseStartBody({ market: "KR", locale: "ko" })).toEqual({ market: "KR", locale: "ko" });
    expect(parseStartBody({ market: "US", locale: null })).toEqual({ market: "US", locale: null });
    expect(parseStartBody({ market: "US" })).toEqual({ market: "US", locale: null });
  });

  it("drops extra fields", () => {
    expect(parseStartBody({ market: "KR", locale: "en", token: "x" })).toEqual({ market: "KR", locale: "en" });
  });

  it("rejects anything else", () => {
    expect(parseStartBody(null)).toBeNull();
    expect(parseStartBody("KR")).toBeNull();
    expect(parseStartBody({ market: "JP", locale: "ko" })).toBeNull();
    expect(parseStartBody({ market: "KR", locale: "fr" })).toBeNull();
  });
});

describe("clientIp", () => {
  it("takes the last X-Forwarded-For entry, the one the ALB appended", () => {
    expect(clientIp("203.0.113.7")).toBe("203.0.113.7");
    expect(clientIp("2001:db8::1")).toBe("2001:db8::1");
  });

  it("ignores addresses the client put in the header itself", () => {
    expect(clientIp("1.2.3.4, 198.51.100.9")).toBe("198.51.100.9");
    expect(clientIp(" spoofed , 5.6.7.8 , 203.0.113.7 ")).toBe("203.0.113.7");
  });

  it("is null without a usable address", () => {
    expect(clientIp(null)).toBeNull();
    expect(clientIp(undefined)).toBeNull();
    expect(clientIp("")).toBeNull();
    expect(clientIp("10.0.0.1, ")).toBeNull();
    expect(clientIp("x".repeat(65))).toBeNull();
  });
});

describe("retry after a 429", () => {
  it("prefers the body, then the header", () => {
    expect(retryAfterSeconds(120, "30")).toBe(120);
    expect(retryAfterSeconds(undefined, "30")).toBe(30);
    expect(retryAfterSeconds("45", null)).toBe(45);
    expect(retryAfterSeconds(12.2, null)).toBe(13);
    expect(retryAfterSeconds(undefined, "Wed, 21 Oct 2026 07:28:00 GMT")).toBeNull();
    expect(retryAfterSeconds(-5, null)).toBeNull();
    expect(retryAfterSeconds(undefined, undefined)).toBeNull();
  });

  it("rounds up to whole minutes, at least one", () => {
    expect(retryMinutes(0)).toBe(1);
    expect(retryMinutes(30)).toBe(1);
    expect(retryMinutes(60)).toBe(1);
    expect(retryMinutes(61)).toBe(2);
    expect(retryMinutes(3600)).toBe(60);
    expect(retryMinutes(null)).toBeNull();
    expect(retryMinutes(Number.NaN)).toBeNull();
  });
});
