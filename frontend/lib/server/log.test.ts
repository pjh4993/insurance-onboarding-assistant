import { describe, expect, it } from "vitest";
import { entryFields, formatLine, truncate } from "./log";

describe("structured log entries", () => {
  it("marks what was cut", () => {
    expect(truncate("abcdef", 10)).toBe("abcdef");
    expect(truncate("abcdef", 4)).toBe("abcd…[+2 chars]");
    expect(truncate("abcdef", 4, "tail")).toBe("…[+2 chars]cdef");
  });

  it("caps string fields and drops undefined ones", () => {
    const fields = entryFields({ "url.path": "p".repeat(50), status: 502, missing: undefined }, undefined, 10);
    expect(fields).toEqual({ "url.path": "p".repeat(10) + "…[+40 chars]", status: 502 });
  });

  it("puts an error in exception.* fields, keeping the stack's tail", () => {
    const err = new Error("the real error");
    err.stack = "Error: the real error\n" + "    at frame\n".repeat(500);
    const fields = entryFields({}, err, 40);
    expect(fields["exception.type"]).toBe("Error");
    expect(fields["exception.message"]).toBe("the real error");
    expect(String(fields["exception.stacktrace"]).startsWith("…[+")).toBe(true);
    expect(String(fields["exception.stacktrace"]).endsWith("    at frame\n")).toBe(true);
  });

  it("writes one JSON object per line", () => {
    const line = formatLine("error", "backend relay failed", { "http.request.method": "GET" });
    expect(line).not.toContain("\n");
    const entry = JSON.parse(line);
    expect(entry).toMatchObject({ level: "ERROR", logger: "onboarding-frontend", msg: "backend relay failed" });
    expect(entry["http.request.method"]).toBe("GET");
    expect(entry.trace_id).toBeUndefined(); // no active span
  });
});
