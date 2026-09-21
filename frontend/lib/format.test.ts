import { describe, expect, it } from "vitest";
import { currencyDigits, formatAgo, formatBillingPeriod, formatMoney, humanize } from "./format";

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
  it("formats billing periods", () => {
    expect(formatBillingPeriod("MONTHLY")).toBe("per month");
    expect(formatBillingPeriod("PER_TRIP")).toBe("per trip");
    expect(formatBillingPeriod("ONE_TIME")).toBe("one-time");
  });

  it("humanizes enum values", () => {
    expect(humanize("PROTECT_DEVICE")).toBe("Protect device");
    expect(humanize("OTP")).toBe("OTP");
    expect(humanize("device_imei")).toBe("Device IMEI");
  });

  it("formats relative time", () => {
    const now = Date.parse("2026-09-21T12:00:00Z");
    expect(formatAgo("2026-09-21T11:59:30Z", now)).toBe("30s ago");
    expect(formatAgo("2026-09-21T11:55:00Z", now)).toBe("5m ago");
    expect(formatAgo("2026-09-21T09:00:00Z", now)).toBe("3h ago");
  });
});
