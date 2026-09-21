import type { SessionView, WaitingFor } from "./types";

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

/**
 * The INTAKE answer to send now, or null. The chat sends what the customer typed or picked on the landing
 * screen ("" when they just pressed start) once the session waits for INTAKE, and only once: `sent` is true
 * after a send was attempted in this tab (kept across reloads by landingStore). A failed send is not
 * retried automatically; the customer can type it in the INTAKE composer instead.
 */
export function intakeToSend({
  waitingFor,
  started,
  sent,
  interest,
}: {
  waitingFor: WaitingFor | undefined;
  started: boolean;
  sent: boolean;
  interest: string;
}): string | null {
  if (waitingFor !== "INTAKE" || !started || sent) return null;
  return interest.trim();
}

// What the customer typed or picked on the landing screen waits in sessionStorage until the session asks
// for INTAKE (after /chat or /s/{token} loads). Keys carry the session ID so a second link opened in the
// same tab starts at its own landing screen. Storage can be missing or throw (private mode, blocked site
// data); the landing screen works without it.
const startedKey = (sessionId: string) => `onb_started:${sessionId}`;
const interestKey = (sessionId: string) => `onb_interest:${sessionId}`;
const intakeKey = (sessionId: string) => `onb_intake_sent:${sessionId}`;

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
      /* storage unavailable: the chat still works, only the landing text is lost on a reload */
    }
  },
  interest(sessionId: string): string {
    try {
      return storage()?.getItem(interestKey(sessionId)) ?? "";
    } catch {
      return "";
    }
  },
  intakeSent(sessionId: string): boolean {
    try {
      return storage()?.getItem(intakeKey(sessionId)) === "1";
    } catch {
      return false;
    }
  },
  markIntakeSent(sessionId: string) {
    try {
      storage()?.setItem(intakeKey(sessionId), "1");
    } catch {
      /* ignore: the chat also keeps this in memory */
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
