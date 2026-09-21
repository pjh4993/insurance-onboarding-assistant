"use client";

import type { InputBody, SessionDetail } from "@/lib/types";
import { Badge } from "../Badge";
import { InputPanel } from "../chat/InputPanel";
import { MessageList } from "../chat/MessageList";
import { STAGE_LABEL, STATUS_LABEL, STATUS_TONE, waitingLabel } from "../labels";

export function Conversation({
  detail,
  me,
  busy,
  assigning,
  onAssign,
  onSubmit,
}: {
  detail: SessionDetail;
  me: string | null;
  busy: boolean;
  assigning: boolean;
  onAssign: () => void;
  onSubmit: (body: InputBody) => Promise<void>;
}) {
  const { session, messages, prompt } = detail;
  const mine = !!me && session.assigned_agent_id === me;
  const lastBotText = [...messages].reverse().find((m) => m.role !== "customer")?.text;

  return (
    <div className="conversation">
      <header className="conversation__header">
        <div>
          <h2>{session.display_name}</h2>
          <div className="session__badges">
            <Badge tone={STATUS_TONE[session.status]}>{STATUS_LABEL[session.status]}</Badge>
            <Badge>{STAGE_LABEL[session.stage]}</Badge>
            {session.waiting_for && (
              <Badge tone={session.waiting_for === "AGENT" ? "warning" : "accent"}>
                Waits: {waitingLabel(session.waiting_for)}
              </Badge>
            )}
            <Badge tone={session.mode === "ASSIST" ? "success" : "muted"}>{session.mode}</Badge>
            <Badge tone="muted">{session.market}</Badge>
          </div>
        </div>
        <div className="conversation__assign">
          {session.assigned_agent_id && !mine && (
            <span className="muted">Assigned to {session.assigned_agent_id}</span>
          )}
          {mine ? (
            <Badge tone="success">Assigned to you</Badge>
          ) : (
            <button className="btn btn--ghost" onClick={onAssign} disabled={assigning}>
              {assigning ? "Assigning…" : "Assign to me"}
            </button>
          )}
        </div>
      </header>
      <section className="conversation__messages">
        <MessageList messages={messages} perspective="agent" busy={busy} />
      </section>
      <footer className="conversation__input">
        <InputPanel
          actor="agent"
          session={session}
          prompt={prompt}
          busy={busy}
          onSubmit={onSubmit}
          showPromptMessage={!!prompt?.message && prompt.message !== lastBotText}
        />
      </footer>
    </div>
  );
}
