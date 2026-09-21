"use client";

import { useTranslations } from "next-intl";
import { sessionLocale } from "@/i18n/locales";
import { useFormat } from "@/i18n/useFormat";
import type { SessionSummary } from "@/lib/types";
import { Badge } from "../Badge";
import { STATUS_TONE } from "../labels";

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
  const t = useTranslations();
  const { ago } = useFormat();
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
            <span className="session__ago">{ago(s.last_activity_at, now)}</span>
          </span>
          <span className="session__badges">
            {handoff && <Badge tone="warning">{t("agent.list.handoff")}</Badge>}
            <Badge tone="neutral">{t(`stage.${s.stage}`)}</Badge>
            {s.waiting_for && !handoff && (
              <Badge tone="accent">{t("agent.list.waits", { what: t(`waiting.${s.waiting_for}`) })}</Badge>
            )}
            {s.status !== "ACTIVE" && s.status !== "HANDOFF" && (
              <Badge tone={STATUS_TONE[s.status]}>{t(`status.${s.status}`)}</Badge>
            )}
            {s.assigned_agent_id && (
              <Badge tone={s.assigned_agent_id === me ? "success" : "muted"} title={s.assigned_agent_id}>
                {s.assigned_agent_id === me ? t("agent.list.mine") : `@${s.assigned_agent_id}`}
              </Badge>
            )}
            <Badge tone="muted">{s.market}</Badge>
            <Badge tone="muted" title={t(`common.localeName.${sessionLocale(s)}`)}>
              {t(`common.localeShort.${sessionLocale(s)}`)}
            </Badge>
          </span>
        </button>
      </li>
    );
  };

  if (sessions.length === 0) {
    return <p className="empty">{t("agent.list.empty")}</p>;
  }
  return (
    <div className="session-list">
      {handoffs.length > 0 && (
        <>
          <h3 className="section-label section-label--warning">{t("agent.list.handoffs", { count: handoffs.length })}</h3>
          <ul>{handoffs.map(item)}</ul>
        </>
      )}
      <h3 className="section-label">{t("agent.list.sessions", { count: rest.length })}</h3>
      <ul>{rest.map(item)}</ul>
    </div>
  );
}
