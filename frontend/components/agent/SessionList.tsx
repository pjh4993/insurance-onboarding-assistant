"use client";

import { formatAgo } from "@/lib/format";
import type { SessionSummary } from "@/lib/types";
import { Badge } from "../Badge";
import { STAGE_LABEL, STATUS_LABEL, STATUS_TONE, waitingLabel } from "../labels";

export function SessionList({
  sessions,
  selectedId,
  onSelect,
  me,
  now,
}: {
  sessions: SessionSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  me: string | null;
  now: number;
}) {
  const handoffs = sessions.filter((s) => s.waiting_for === "AGENT");
  const rest = sessions.filter((s) => s.waiting_for !== "AGENT");

  const item = (s: SessionSummary) => {
    const handoff = s.waiting_for === "AGENT";
    return (
      <li key={s.session_id}>
        <button
          className={`session ${handoff ? "session--handoff" : ""} ${s.session_id === selectedId ? "session--selected" : ""}`}
          onClick={() => onSelect(s.session_id)}
          aria-current={s.session_id === selectedId}
        >
          <span className="session__top">
            <strong className="session__name">{s.display_name}</strong>
            <span className="session__ago">{formatAgo(s.last_activity_at, now)}</span>
          </span>
          <span className="session__badges">
            {handoff && <Badge tone="warning">Handoff</Badge>}
            <Badge tone="neutral">{STAGE_LABEL[s.stage]}</Badge>
            {s.waiting_for && !handoff && <Badge tone="accent">Waits: {waitingLabel(s.waiting_for)}</Badge>}
            {s.status !== "ACTIVE" && s.status !== "HANDOFF" && (
              <Badge tone={STATUS_TONE[s.status]}>{STATUS_LABEL[s.status]}</Badge>
            )}
            {s.assigned_agent_id && (
              <Badge tone={s.assigned_agent_id === me ? "success" : "muted"} title={s.assigned_agent_id}>
                {s.assigned_agent_id === me ? "Mine" : `@${s.assigned_agent_id}`}
              </Badge>
            )}
            <Badge tone="muted">{s.market}</Badge>
          </span>
        </button>
      </li>
    );
  };

  if (sessions.length === 0) {
    return <p className="empty">No sessions yet. Create one to get a customer link.</p>;
  }
  return (
    <div className="session-list">
      {handoffs.length > 0 && (
        <>
          <h3 className="section-label section-label--warning">Handoff requests · {handoffs.length}</h3>
          <ul>{handoffs.map(item)}</ul>
        </>
      )}
      <h3 className="section-label">Sessions · {rest.length}</h3>
      <ul>{rest.map(item)}</ul>
    </div>
  );
}
