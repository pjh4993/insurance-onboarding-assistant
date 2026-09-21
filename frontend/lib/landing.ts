import type { SessionView } from "./types";

/**
 * The landing screen is for a customer who has not started yet: the session is active, still at the
 * first stage, and the customer has not said anything. Once they start (or come back after answering),
 * they go straight to the chat.
 */
export function shouldShowLanding(view: SessionView, started: boolean): boolean {
  if (started) return false;
  const { session, messages } = view;
  return session.status === "ACTIVE" && session.stage === "IDENTITY" && !messages.some((m) => m.role === "customer");
}

// What the customer typed or picked on the landing screen. The graph asks for identity first, so this
// waits in sessionStorage and pre-fills the first profiling answer (NEEDS). Keys carry the session ID so a
// second link opened in the same tab starts at its own landing screen. Storage can be missing or throw
// (private mode, blocked site data); the landing screen works without it.
const startedKey = (sessionId: string) => `onb_started:${sessionId}`;
const interestKey = (sessionId: string) => `onb_interest:${sessionId}`;

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export const landingStore = {
  started(sessionId: string): boolean {
    try {
      return storage()?.getItem(startedKey(sessionId)) === "1";
    } catch {
      return false;
    }
  },
  start(sessionId: string, interest: string) {
    try {
      const s = storage();
      s?.setItem(startedKey(sessionId), "1");
      if (interest) s?.setItem(interestKey(sessionId), interest);
      else s?.removeItem(interestKey(sessionId));
    } catch {
      /* storage unavailable: the chat still works, only the pre-fill is lost */
    }
  },
  interest(sessionId: string): string {
    try {
      return storage()?.getItem(interestKey(sessionId)) ?? "";
    } catch {
      return "";
    }
  },
  clearInterest(sessionId: string) {
    try {
      storage()?.removeItem(interestKey(sessionId));
    } catch {
      /* ignore */
    }
  },
};
