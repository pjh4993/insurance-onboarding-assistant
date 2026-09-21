import { describe, expect, it } from "vitest";
import { agoParts, currencyDigits, formatDate, formatMoney, humanize } from "./format";

describe("formatMoney", () => {
  it("treats KRW minor units as whole won (0 decimals)", () => {
    expect(currencyDigits("KRW")).toBe(0);
    expect(formatMoney(4900, "KRW")).toBe("₩4,900");
  });

  it("divides USD minor units by 100", () => {
    expect(currencyDigits("USD")).toBe(2);
    expect(formatMoney(1299, "USD")).toBe("$12.99");
    expect(formatMoney(129900, "USD")).toBe("$1,299.00");
    expect(formatMoney(0, "USD")).toBe("$0.00");
  });

  it("handles 3-decimal currencies", () => {
    expect(currencyDigits("KWD")).toBe(3);
    expect(formatMoney(1500, "KWD")).toMatch(/1\.500/);
  });

  it("falls back for an unknown currency code", () => {
    expect(formatMoney(1000, "ZZ")).toBe("10.00 ZZ");
  });
});

describe("labels", () => {
  it("humanizes enum values", () => {
    expect(humanize("PROTECT_DEVICE")).toBe("Protect device");
    expect(humanize("OTP")).toBe("OTP");
    expect(humanize("device_imei")).toBe("Device IMEI");
  });

  it("splits relative time into a unit and a count", () => {
    const now = Date.parse("2026-09-21T12:00:00Z");
    expect(agoParts("2026-09-21T11:59:30Z", now)).toEqual({ unit: "seconds", n: 30 });
    expect(agoParts("2026-09-21T11:55:00Z", now)).toEqual({ unit: "minutes", n: 5 });
    expect(agoParts("2026-09-21T09:00:00Z", now)).toEqual({ unit: "hours", n: 3 });
    expect(agoParts("2026-09-18T12:00:00Z", now)).toEqual({ unit: "days", n: 3 });
    expect(agoParts("not a date", now)).toBeNull();
  });

  it("formats dates in the given locale", () => {
    expect(formatDate("2026-09-21T10:00:00Z", "en-US")).toBe("Sep 21, 2026");
    expect(formatDate("2026-09-21T10:00:00Z", "ko-KR")).toMatch(/2026.*9.*21/);
  });
});
