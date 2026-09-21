// Pure helpers for applying SSE events to client state (unit-tested).
import type { Message, SessionSummary } from "./types";

/** Append a message unless one with the same id is already present; keep chronological order. */
export function appendMessage(messages: Message[], message: Message): Message[] {
  if (messages.some((m) => m.id === message.id)) return messages;
  const next = [...messages, message];
  next.sort((a, b) => a.created_at.localeCompare(b.created_at));
  return next;
}

/** Contract order: waiting_for == "AGENT" first, then oldest last_activity_at. */
export function sortSessions(sessions: SessionSummary[]): SessionSummary[] {
  return [...sessions].sort((a, b) => {
    const ha = a.waiting_for === "AGENT" ? 0 : 1;
    const hb = b.waiting_for === "AGENT" ? 0 : 1;
    if (ha !== hb) return ha - hb;
    return a.last_activity_at.localeCompare(b.last_activity_at);
  });
}

export function upsertSession(sessions: SessionSummary[], s: SessionSummary): SessionSummary[] {
  const i = sessions.findIndex((x) => x.session_id === s.session_id);
  const next = i === -1 ? [...sessions, s] : sessions.map((x, j) => (j === i ? s : x));
  return sortSessions(next);
}

export function isClosed(status: SessionSummary["status"]): boolean {
  return status !== "ACTIVE" && status !== "HANDOFF";
}
