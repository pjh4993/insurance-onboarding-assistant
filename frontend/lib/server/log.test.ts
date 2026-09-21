import { describe, expect, it } from "vitest";
import { formatLine, truncate } from "./log";

describe("log length cap", () => {
  it("marks what was cut", () => {
    expect(truncate("abcdef", 10)).toBe("abcdef");
    expect(truncate("abcdef", 4)).toBe("abcd…[+2 chars]");
    expect(truncate("abcdef", 4, "tail")).toBe("…[+2 chars]cdef");
  });

  it("caps the message head and keeps the stack tail", () => {
    const err = new Error("the real error");
    err.stack = "Error: the real error\n" + "    at frame\n".repeat(500);
    const line = formatLine("x".repeat(100), err, 40);
    const [head, stack] = line.split("\n", 2);
    expect(head).toBe("x".repeat(40) + "…[+60 chars]");
    expect(stack.startsWith("…[+")).toBe(true);
    expect(line.endsWith("    at frame\n")).toBe(true);
  });
});
