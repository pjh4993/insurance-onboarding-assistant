"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, customerApi } from "@/lib/api";
import { appendMessage } from "@/lib/session";
import type { InputBody, SessionView } from "@/lib/types";
import { useEventStream } from "@/lib/useEventStream";
import { InputPanel } from "../chat/InputPanel";
import { MessageList } from "../chat/MessageList";
import { StageStrip } from "../StageStrip";

const BUSY_TIMEOUT_MS = 30_000;

export function CustomerChat() {
  const [view, setView] = useState<SessionView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    customerApi
      .getSession()
      .then((v) => {
        setView(v);
        setError(null);
      })
      .catch((e: unknown) => {
        setError(
          e instanceof ApiError && (e.status === 401 || e.status === 403 || e.status === 404)
            ? "This link has expired or is not valid. Please ask for a new link."
            : "We could not load your session. Please refresh the page.",
        );
      });
  }, []);

  useEffect(load, [load]);

  // Stop the typing indicator if the assistant never answers (e.g. the stream dropped).
  useEffect(() => {
    if (!busy) return;
    const t = setTimeout(() => setBusy(false), BUSY_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [busy]);

  const stream = useEventStream(view ? customerApi.streamUrl : null, {
    onOpen: load, // resync anything missed while disconnected
    "session.updated": ({ session }) => setView((v) => v && { ...v, session }),
    "message.appended": ({ message }) => {
      setView((v) => v && { ...v, messages: appendMessage(v.messages, message) });
      if (message.role !== "customer") setBusy(false);
    },
    "prompt.updated": ({ prompt }) => {
      setView((v) => v && { ...v, prompt });
      setBusy(false);
    },
  });

  async function submit(body: InputBody) {
    await customerApi.sendInput(body);
    setBusy(true);
  }

  if (error) {
    return (
      <main className="customer customer--center">
        <div className="notice">
          <h1>Something went wrong</h1>
          <p>{error}</p>
        </div>
      </main>
    );
  }
  if (!view) {
    return (
      <main className="customer customer--center">
        <p className="muted">Loading your session…</p>
      </main>
    );
  }

  const { session, messages, prompt } = view;
  const lastBotText = [...messages].reverse().find((m) => m.role !== "customer")?.text;

  return (
    <main className="customer">
      <header className="customer__header">
        <div className="brand">
          <span className="brand__mark" aria-hidden>
            ◆
          </span>
          <div>
            <strong>Cover Assistant</strong>
            <span className="brand__sub">Protection for what you just bought · {session.market}</span>
          </div>
        </div>
        {stream === "reconnecting" && <span className="conn">Reconnecting…</span>}
      </header>
      <div className="customer__progress">
        <StageStrip stage={session.stage} compact />
      </div>
      <section className="customer__chat">
        <MessageList messages={messages} perspective="customer" busy={busy} />
      </section>
      <footer className="customer__input">
        <InputPanel
          actor="customer"
          session={session}
          prompt={prompt}
          busy={busy}
          onSubmit={submit}
          showPromptMessage={!!prompt?.message && prompt.message !== lastBotText}
        />
      </footer>
    </main>
  );
}
