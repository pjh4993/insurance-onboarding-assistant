"use client";

import { useTranslations } from "next-intl";
import { sessionLocale } from "@/i18n/locales";
import type { InputBody, SessionDetail } from "@/lib/types";
import { Badge } from "../Badge";
import { InputPanel } from "../chat/InputPanel";
import { MessageList } from "../chat/MessageList";
import { STATUS_TONE } from "../labels";

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
  const t = useTranslations();
  const { session, messages, prompt } = detail;
  const mine = !!me && session.assigned_agent_id === me;
  const lastBotText = [...messages].reverse().find((m) => m.role !== "customer")?.text;

  return (
    <div className="conversation">
      <header className="conversation__header">
        <div>
          <h2>{session.display_name}</h2>
          <div className="session__badges">
            <Badge tone={STATUS_TONE[session.status]}>{t(`status.${session.status}`)}</Badge>
            <Badge>{t(`stage.${session.stage}`)}</Badge>
            {session.waiting_for && (
              <Badge tone={session.waiting_for === "AGENT" ? "warning" : "accent"}>
                {t("agent.conversation.waits", { what: t(`waiting.${session.waiting_for}`) })}
              </Badge>
            )}
            <Badge tone={session.mode === "ASSIST" ? "success" : "muted"}>{session.mode}</Badge>
            {session.origin && (
              <Badge tone={session.origin === "SELF_SERVE" ? "accent" : "muted"}>
                {t(`agent.list.origin.${session.origin}`)}
              </Badge>
            )}
            <Badge tone="muted">{session.market}</Badge>
            <Badge tone="muted">{t(`common.localeName.${sessionLocale(session)}`)}</Badge>
          </div>
        </div>
        <div className="conversation__assign">
          {session.assigned_agent_id && !mine && (
            <span className="muted">{t("agent.conversation.assignedTo", { agent: session.assigned_agent_id })}</span>
          )}
          {mine ? (
            <Badge tone="success">{t("agent.conversation.assignedToYou")}</Badge>
          ) : (
            <button className="btn btn--ghost" onClick={onAssign} disabled={assigning}>
              {assigning ? t("agent.conversation.assigning") : t("agent.conversation.assign")}
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
