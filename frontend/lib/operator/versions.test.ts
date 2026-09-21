import { describe, expect, it } from "vitest";
import { changeCount, jsonError, lineDiff, nextVersion, prettyJson, timeAgo, withContext } from "./versions";

describe("nextVersion", () => {
  it("bumps the latest version of the draft's major, as the backend does", () => {
    const published = ["1.0.0", "1.2.0", "1.10.1", "2.0.0"];
    expect(nextVersion(published, "1.0.0", "patch")).toBe("1.10.2");
    expect(nextVersion(published, "1.2.0", "minor")).toBe("1.11.0");
    expect(nextVersion(published, "3.0.0", "patch")).toBe("3.0.0");
  });
});

describe("lineDiff", () => {
  it("marks added and removed lines with their line numbers", () => {
    const diff = lineDiff("a\nb\nc", "a\nB\nc\nd");
    expect(diff.map((l) => `${l.kind}:${l.text}`)).toEqual(["same:a", "del:b", "add:B", "same:c", "add:d"]);
    expect(diff[2]).toMatchObject({ kind: "add", b: 2 });
    expect(changeCount(diff)).toEqual({ added: 2, removed: 1 });
  });

  it("folds unchanged runs outside the context into gaps", () => {
    const a = Array.from({ length: 20 }, (_, i) => `line ${i}`).join("\n");
    const b = a.replace("line 10", "LINE 10");
    const rows = withContext(lineDiff(a, b), 2);
    expect(rows[0]).toEqual({ kind: "gap", count: 8 });
    expect(rows.filter((r) => r.kind !== "gap")).toHaveLength(6);
    expect(rows.at(-1)).toEqual({ kind: "gap", count: 7 }); // 21 diff lines: 8 folded, 6 shown, 7 folded
  });
});

describe("json helpers", () => {
  it("re-indents JSON so diffs show content only, and names syntax errors", () => {
    expect(prettyJson('{"a":1}')).toBe('{\n  "a": 1\n}');
    expect(prettyJson("not json")).toBe("not json");
    expect(jsonError('{"a":1}')).toBeNull();
    expect(jsonError('{"a":')).toMatch(/JSON/);
  });
});

describe("timeAgo", () => {
  it("says how long ago", () => {
    const now = Date.parse("2026-09-22T00:00:00Z");
    expect(timeAgo("2026-09-21T23:57:00Z", now)).toBe("3 minutes ago");
    expect(timeAgo("2026-09-20T00:00:00Z", now)).toBe("2 days ago");
    expect(timeAgo("2026-09-22T00:00:00Z", now)).toBe("just now");
    expect(timeAgo(undefined, now)).toBe("");
  });
});
