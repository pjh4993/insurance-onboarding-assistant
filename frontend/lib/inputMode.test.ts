import { describe, expect, it } from "vitest";
import { inputKindFor } from "./inputMode";
import type { WaitingFor } from "./types";

describe("inputKindFor", () => {
  const cases: [WaitingFor, string, string][] = [
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

  it("treats a missing prompt as nothing to answer", () => {
    expect(inputKindFor(undefined, "customer")).toBe("none");
  });
});
