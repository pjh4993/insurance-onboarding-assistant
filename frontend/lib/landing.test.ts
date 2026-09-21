import { describe, expect, it } from "vitest";
import { shouldShowLanding } from "./landing";
import type { Message, SessionView } from "./types";

const greeting: Message = { id: "g", role: "assistant", text: "hi", created_at: "2026-09-21T10:00:00Z" };
const view = (over: Partial<SessionView["session"]> = {}, messages: Message[] = [greeting]): SessionView => ({
  session: {
    session_id: "s",
    display_name: "Unverified #s",
    market: "KR",
    status: "ACTIVE",
    stage: "IDENTITY",
    waiting_for: "IDENTITY_INFO",
    mode: "AUTO",
    assigned_agent_id: null,
    last_activity_at: "2026-09-21T10:00:00Z",
    ...over,
  },
  messages,
  prompt: null,
});

describe("shouldShowLanding", () => {
  it("shows for a fresh session", () => {
    expect(shouldShowLanding(view(), false)).toBe(true);
  });

  it("hides once the customer started on this device", () => {
    expect(shouldShowLanding(view(), true)).toBe(false);
  });

  it("hides once the customer has said anything", () => {
    const said: Message = { ...greeting, id: "c", role: "customer" };
    expect(shouldShowLanding(view({}, [greeting, said]), false)).toBe(false);
  });

  it("hides past identity or on a closed session", () => {
    expect(shouldShowLanding(view({ stage: "PROFILING" }), false)).toBe(false);
    expect(shouldShowLanding(view({ status: "EXPIRED" }), false)).toBe(false);
  });
});
