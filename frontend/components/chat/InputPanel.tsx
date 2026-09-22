"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { inputKindFor, type Actor } from "@/lib/inputMode";
import { isClosed } from "@/lib/session";
import type { InputBody, Prompt, SessionSummary } from "@/lib/types";
import { ConfirmPanel, DecisionPanel, HandoffPanel, IdentityForm, OtpForm, TextComposer } from "./forms";
import { TopicForm } from "./TopicForm";

/**
 * The input area under the chat. It switches on `prompt.waiting_for` (falling back to the session's
 * `waiting_for` when there is no prompt payload) and on who is typing.
 */
export function InputPanel({
  actor,
  session,
  prompt,
  busy,
  onSubmit,
  showPromptMessage,
  intakeDraft,
}: {
  actor: Actor;
  session: SessionSummary;
  prompt: Prompt | null;
  busy: boolean;
  onSubmit: (body: InputBody) => Promise<void>;
  showPromptMessage: boolean;
  /** Pre-fills the INTAKE composer (shown only if the chat could not send the landing text itself). */
  intakeDraft?: string;
}) {
  const t = useTranslations();
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const waitingFor = prompt ? prompt.waiting_for : session.waiting_for;
  const form = prompt?.form;
  const kind = inputKindFor(waitingFor, actor, !!form);
  const disabled = busy || sending;

  // Child forms reset themselves only when this resolves true, so a failed send keeps what was typed.
  async function safeSubmit(body: InputBody): Promise<boolean> {
    setError(null);
    setSending(true);
    try {
      await onSubmit(body);
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("input.sendFailed"));
      return false;
    } finally {
      setSending(false);
    }
  }

  if (isClosed(session.status) && kind === "none") {
    return (
      <div className="input-panel input-panel--closed">
        {t("input.closed", { status: t(`status.${session.status}`) })}
      </div>
    );
  }

  let body: React.ReactNode = null;
  switch (kind) {
    case "identity":
      body = <IdentityForm market={session.market} onSubmit={safeSubmit} disabled={disabled} />;
      break;
    case "topic-form": {
      const w = waitingFor as "IDENTITY_INFO" | "NEEDS";
      body = form && (
        <TopicForm
          // A new form (next topic, or new pre-filled values) starts from its own values.
          key={`${w}:${JSON.stringify(form)}`}
          form={form}
          type={w}
          onSubmit={safeSubmit}
          disabled={disabled}
          stepped={actor === "customer"}
          textPlaceholder={
            actor === "agent" ? t("input.agentPlaceholder", { kind: t("waiting.NEEDS") }) : t("input.placeholder.NEEDS")
          }
        />
      );
      break;
    }
    case "otp":
      body = <OtpForm onSubmit={safeSubmit} disabled={disabled} />;
      break;
    case "text": {
      const w = waitingFor as "INTAKE" | "NEEDS" | "PARTIES" | "ANSWERS";
      body = (
        <TextComposer
          disabled={disabled}
          placeholder={
            actor === "agent" ? t("input.agentPlaceholder", { kind: t(`waiting.${w}`) }) : t(`input.placeholder.${w}`)
          }
          initialText={w === "INTAKE" ? intakeDraft : undefined}
          onSend={(text) => safeSubmit({ type: w, data: { text } })}
        />
      );
      break;
    }
    case "decision":
      body = <DecisionPanel options={prompt?.options ?? []} onSubmit={safeSubmit} disabled={disabled} />;
      break;
    case "confirm":
      body = <ConfirmPanel summary={prompt?.summary} onSubmit={safeSubmit} disabled={disabled} />;
      break;
    case "handoff":
      body = <HandoffPanel onSubmit={safeSubmit} disabled={disabled} />;
      break;
    case "wait-agent":
      body = <p className="waiting">{t("input.waitAgent")}</p>;
      break;
    case "wait-customer":
      body = <p className="waiting">{t("input.waitCustomer")}</p>;
      break;
    case "none":
      body = <p className="waiting">{busy ? t("input.working") : t("input.nothing")}</p>;
      break;
  }

  return (
    <div className={`input-panel input-panel--${kind}`}>
      {showPromptMessage && prompt?.message && <p className="input-panel__prompt">{prompt.message}</p>}
      {body}
      {error && (
        <p className="input-panel__error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
