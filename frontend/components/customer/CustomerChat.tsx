"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, customerApi } from "@/lib/api";
import { landingStore, shouldShowLanding } from "@/lib/landing";
import { appendMessage } from "@/lib/session";
import type { InputBody, SessionView } from "@/lib/types";
import { useEventStream } from "@/lib/useEventStream";
import { InputPanel } from "../chat/InputPanel";
import { MessageList } from "../chat/MessageList";
import { StageStrip } from "../StageStrip";
import { customerCopy } from "./copy";
import { Landing } from "./Landing";

const BUSY_TIMEOUT_MS = 30_000;

export function CustomerChat() {
  const [view, setView] = useState<SessionView | null>(null);
  const [error, setError] = useState<"expired" | "loadFailed" | null>(null);
  const [busy, setBusy] = useState(false);
  // Set when the customer leaves the landing screen in this render; a reload reads it from landingStore.
  const [startedNow, setStartedNow] = useState(false);

  const load = useCallback(() => {
    customerApi
      .getSession()
      .then((v) => {
        setView(v);
        setError(null);
      })
      .catch((e: unknown) => {
        setError(
          e instanceof ApiError && (e.status === 401 || e.status === 403 || e.status === 404) ? "expired" : "loadFailed",
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
    if (body.type === "NEEDS" && view) landingStore.clearInterest(view.session.session_id);
    setBusy(true);
  }

  function start(interest: string) {
    if (view) landingStore.start(view.session.session_id, interest);
    setStartedNow(true);
  }

  if (error) {
    // The market is unknown until the session loads, so the error follows the browser's language.
    const c = customerCopy(navigator.language.toLowerCase().startsWith("ko") ? "KR" : "US");
    return (
      <main className="customer customer--center">
        <div className="notice">
          <h1>{c.errorTitle}</h1>
          <p>{c[error]}</p>
        </div>
      </main>
    );
  }
  if (!view) {
    return (
      <main className="customer customer--center" aria-busy>
        <span className="spinner" aria-label="Loading" />
      </main>
    );
  }

  const { session, messages, prompt } = view;
  const c = customerCopy(session.market);
  // Only reached after the session loads on the client, so reading sessionStorage here is hydration-safe.
  if (shouldShowLanding(view, startedNow || landingStore.started(session.session_id))) {
    return <Landing market={session.market} onStart={start} />;
  }
  const lastBotText = [...messages].reverse().find((m) => m.role !== "customer")?.text;

  return (
    <main className="customer customer--chat" lang={c.lang}>
      <header className="customer__header">
        <div className="brand">
          <span className="brand__mark" aria-hidden>
            ◆
          </span>
          <div>
            <strong>Cover Assistant</strong>
            <span className="brand__sub">{c.sub(session.market)}</span>
          </div>
        </div>
        <StageStrip stage={session.stage} compact />
        {stream === "reconnecting" && <span className="conn">{c.reconnecting}</span>}
      </header>
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
          needsDraft={landingStore.interest(session.session_id)}
        />
      </footer>
    </main>
  );
}
