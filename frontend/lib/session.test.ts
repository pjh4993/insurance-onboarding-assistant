import { describe, expect, it } from "vitest";
import { appendMessage, sortSessions, upsertSession } from "./session";
import type { Message, SessionSummary } from "./types";

const msg = (id: string, at: string): Message => ({ id, role: "assistant", text: id, created_at: at });
const sess = (id: string, at: string, waiting_for: SessionSummary["waiting_for"] = "NEEDS"): SessionSummary => ({
  session_id: id,
  display_name: id,
  market: "KR",
  status: "ACTIVE",
  stage: "PROFILING",
  waiting_for,
  mode: "AUTO",
  assigned_agent_id: null,
  last_activity_at: at,
});

describe("appendMessage", () => {
  it("dedupes by id and keeps time order", () => {
    const a = msg("a", "2026-09-21T10:00:00Z");
    const b = msg("b", "2026-09-21T10:01:00Z");
    expect(appendMessage([b], a).map((m) => m.id)).toEqual(["a", "b"]);
    const same = [a];
    expect(appendMessage(same, a)).toBe(same);
  });
});

describe("session ordering", () => {
  it("puts handoffs first, then oldest activity", () => {
    const list = sortSessions([
      sess("new", "2026-09-21T10:05:00Z"),
      sess("old", "2026-09-21T10:00:00Z"),
      sess("handoff", "2026-09-21T10:09:00Z", "AGENT"),
    ]);
    expect(list.map((s) => s.session_id)).toEqual(["handoff", "old", "new"]);
  });

  it("upserts and re-sorts", () => {
    const list = [sess("a", "2026-09-21T10:00:00Z"), sess("b", "2026-09-21T10:01:00Z")];
    const next = upsertSession(list, sess("b", "2026-09-21T10:02:00Z", "AGENT"));
    expect(next.map((s) => s.session_id)).toEqual(["b", "a"]);
    expect(upsertSession(next, sess("c", "2026-09-21T09:00:00Z")).map((s) => s.session_id)).toEqual(["b", "c", "a"]);
  });
});
