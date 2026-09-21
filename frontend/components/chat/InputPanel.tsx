"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { inputKindFor, TEXT_PLACEHOLDER, type Actor } from "@/lib/inputMode";
import { isClosed } from "@/lib/session";
import type { InputBody, Prompt, SessionSummary } from "@/lib/types";
import { STATUS_LABEL } from "../labels";
import { ConfirmPanel, DecisionPanel, HandoffPanel, IdentityForm, OtpForm, TextComposer } from "./forms";

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
  needsDraft,
}: {
  actor: Actor;
  session: SessionSummary;
  prompt: Prompt | null;
  busy: boolean;
  onSubmit: (body: InputBody) => Promise<void>;
  showPromptMessage: boolean;
  /** Pre-fills the first profiling answer, e.g. what the customer picked on the landing screen. */
  needsDraft?: string;
}) {
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const waitingFor = prompt ? prompt.waiting_for : session.waiting_for;
  const kind = inputKindFor(waitingFor, actor);
  const disabled = busy || sending;

  // Child forms reset themselves only when this resolves true, so a failed send keeps what was typed.
  async function safeSubmit(body: InputBody): Promise<boolean> {
    setError(null);
    setSending(true);
    try {
      await onSubmit(body);
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send. Please try again.");
      return false;
    } finally {
      setSending(false);
    }
  }

  if (isClosed(session.status) && kind === "none") {
    return (
      <div className="input-panel input-panel--closed">
        Session {STATUS_LABEL[session.status].toLowerCase()}.
      </div>
    );
  }

  let body: React.ReactNode = null;
  switch (kind) {
    case "identity":
      body = <IdentityForm market={session.market} onSubmit={safeSubmit} disabled={disabled} />;
      break;
    case "otp":
      body = <OtpForm onSubmit={safeSubmit} disabled={disabled} />;
      break;
    case "text": {
      const w = waitingFor as "NEEDS" | "PARTIES" | "ANSWERS";
      body = (
        <TextComposer
          disabled={disabled}
          placeholder={actor === "agent" ? `Answer as agent (${w.toLowerCase()})…` : TEXT_PLACEHOLDER[w]}
          initialText={w === "NEEDS" ? needsDraft : undefined}
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
      body = <p className="waiting">An agent will join this conversation shortly. You can keep this page open.</p>;
      break;
    case "wait-customer":
      body = <p className="waiting">Waiting for the customer to enter their identity details or code.</p>;
      break;
    case "none":
      body = <p className="waiting">{busy ? "Working on it…" : "Nothing to answer right now."}</p>;
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
