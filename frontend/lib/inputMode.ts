import type { WaitingFor } from "./types";

export type Actor = "customer" | "agent";

/** Which input component the chat shows for a given `prompt.waiting_for`. */
export type InputKind =
  | "identity" // IDENTITY_INFO form (backends without topic forms)
  | "topic-form" // a small topic form from prompt.form (IDENTITY_INFO, NEEDS)
  | "otp" // OTP code
  | "text" // free text: INTAKE, NEEDS, PARTIES, ANSWERS
  | "decision" // recommendation cards with Accept / Decline / Change
  | "confirm" // summary with Confirm / Fix something
  | "handoff" // agent resolves a handoff: Verified / Continue / End
  | "wait-agent" // customer waits for a human agent
  | "wait-customer" // agent waits for the customer to enter something private
  | "none"; // nothing to answer (working, or the session is closed)

export function inputKindFor(waitingFor: WaitingFor | undefined, actor: Actor, hasForm = false): InputKind {
  switch (waitingFor) {
    case "IDENTITY_INFO":
      // Identity details and OTP codes are the customer's to enter; the agent resolves failures via AGENT.
      if (actor !== "customer") return "wait-customer";
      return hasForm ? "topic-form" : "identity";
    case "OTP_CODE":
      return actor === "customer" ? "otp" : "wait-customer";
    case "NEEDS":
      return hasForm ? "topic-form" : "text";
    case "INTAKE": // the chat sends the landing text itself; this is the fallback composer
    case "PARTIES":
    case "ANSWERS":
      return "text";
    case "DECISION":
      return "decision";
    case "CONFIRM":
      return "confirm";
    case "AGENT":
      return actor === "agent" ? "handoff" : "wait-agent";
    default:
      return "none";
  }
}
