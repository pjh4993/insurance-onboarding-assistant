import type { SessionStatus } from "@/lib/types";
import type { Tone } from "./Badge";

// Label text lives in messages/*.json (stage.*, waiting.*, status.*); only the badge tones are here.
export const STATUS_TONE: Record<SessionStatus, Tone> = {
  ACTIVE: "accent",
  SUBMITTED: "success",
  DECLINED: "muted",
  WITHDRAWN: "muted",
  HANDOFF: "warning",
  EXPIRED: "muted",
};
