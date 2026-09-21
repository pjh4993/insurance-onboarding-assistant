import { describe, expect, it } from "vitest";
import { inputKindFor } from "./inputMode";
import type { WaitingFor } from "./types";

describe("inputKindFor", () => {
  const cases: [WaitingFor, string, string][] = [
    ["INTAKE", "text", "text"],
    ["IDENTITY_INFO", "identity", "wait-customer"],
    ["OTP_CODE", "otp", "wait-customer"],
    ["NEEDS", "text", "text"],
    ["PARTIES", "text", "text"],
    ["ANSWERS", "text", "text"],
    ["DECISION", "decision", "decision"],
    ["CONFIRM", "confirm", "confirm"],
    ["AGENT", "wait-agent", "handoff"],
    [null, "none", "none"],
  ];

  it.each(cases)("%s -> customer %s, agent %s", (waitingFor, customer, agent) => {
    expect(inputKindFor(waitingFor, "customer")).toBe(customer);
    expect(inputKindFor(waitingFor, "agent")).toBe(agent);
  });

  it("shows a topic form for IDENTITY_INFO and NEEDS when the prompt has one", () => {
    expect(inputKindFor("IDENTITY_INFO", "customer", true)).toBe("topic-form");
    expect(inputKindFor("NEEDS", "customer", true)).toBe("topic-form");
    expect(inputKindFor("NEEDS", "agent", true)).toBe("topic-form");
    // Identity stays the customer's to enter.
    expect(inputKindFor("IDENTITY_INFO", "agent", true)).toBe("wait-customer");
    expect(inputKindFor("PARTIES", "customer", true)).toBe("text");
  });

  it("treats a missing prompt as nothing to answer", () => {
    expect(inputKindFor(undefined, "customer")).toBe("none");
  });
});
