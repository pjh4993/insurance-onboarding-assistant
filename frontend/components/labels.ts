import type { SessionStatus, Stage, WaitingFor } from "@/lib/types";
import type { Tone } from "./Badge";

export const STAGE_LABEL: Record<Stage, string> = {
  IDENTITY: "Identity",
  PROFILING: "Profiling",
  RECOMMENDATION: "Recommendation",
  APPLICATION: "Application",
  SUBMITTED: "Submitted",
  HANDOFF: "Handoff",
  DECLINED: "Declined",
  WITHDRAWN: "Withdrawn",
};

export const WAITING_LABEL: Record<Exclude<WaitingFor, null>, string> = {
  IDENTITY_INFO: "Identity details",
  OTP_CODE: "OTP code",
  NEEDS: "Needs",
  DECISION: "Decision",
  PARTIES: "Parties",
  ANSWERS: "Answers",
  CONFIRM: "Confirmation",
  AGENT: "Agent",
};

export function waitingLabel(w: WaitingFor): string {
  return w ? WAITING_LABEL[w] : "Nothing";
}

export const STATUS_TONE: Record<SessionStatus, Tone> = {
  ACTIVE: "accent",
  SUBMITTED: "success",
  DECLINED: "muted",
  WITHDRAWN: "muted",
  HANDOFF: "warning",
  EXPIRED: "muted",
};

export const STATUS_LABEL: Record<SessionStatus, string> = {
  ACTIVE: "Active",
  SUBMITTED: "Submitted",
  DECLINED: "Declined",
  WITHDRAWN: "Withdrawn",
  HANDOFF: "Handoff",
  EXPIRED: "Expired",
};
