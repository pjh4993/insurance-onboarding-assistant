"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";
import { useFormat } from "@/i18n/useFormat";
import type { Message } from "@/lib/types";

/**
 * `perspective` decides which side is "mine": the customer sees their own messages on the right;
 * the agent sees assistant and agent messages on the right.
 */
export function MessageList({
  messages,
  perspective,
  busy,
}: {
  messages: Message[];
  perspective: "customer" | "agent";
  busy?: boolean;
}) {
  const t = useTranslations();
  const { time } = useFormat();
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, busy]);

  return (
    <div className="messages" role="log" aria-live="polite">
      {messages.length === 0 && !busy && <p className="messages__empty">{t("messages.empty")}</p>}
      {messages.map((m) => {
        if (m.role === "system") {
          return (
            <div key={m.id} className="msg msg--system">
              {m.text}
            </div>
          );
        }
        const mine = perspective === "customer" ? m.role === "customer" : m.role !== "customer";
        const label = t(`role.${m.role}`);
        return (
          <div key={m.id} className={`msg msg--${m.role} ${mine ? "msg--mine" : ""}`}>
            <div className="msg__meta">
              <span>{label}</span>
              <time dateTime={m.created_at}>{time(m.created_at)}</time>
            </div>
            <div className="msg__bubble">{m.text}</div>
          </div>
        );
      })}
      {busy && (
        <div className="msg msg--assistant">
          <div className="msg__bubble typing" aria-label={t("messages.working")}>
            <span />
            <span />
            <span />
          </div>
        </div>
      )}
      <div ref={end} />
    </div>
  );
}
