"use client";

import Link from "next/link";
import { NextIntlClientProvider, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { sessionLocale, type Locale } from "@/i18n/locales";
import { MESSAGES } from "@/i18n/messages";
import { ApiError, customerApi } from "@/lib/api";
import { landingStore, shouldShowLanding } from "@/lib/landing";
import { appendMessage } from "@/lib/session";
import type { InputBody, SessionView } from "@/lib/types";
import { useEventStream } from "@/lib/useEventStream";
import { InputPanel } from "../chat/InputPanel";
import { MessageList } from "../chat/MessageList";
import { LocaleSwitch } from "../LocaleSwitch";
import { StageStrip } from "../StageStrip";
import { Landing } from "./Landing";

const BUSY_TIMEOUT_MS = 30_000;

export function CustomerChat() {
  const [view, setView] = useState<SessionView | null>(null);
  const [error, setError] = useState<"expired" | "loadFailed" | null>(null);
  const [busy, setBusy] = useState(false);
  // Set when the customer leaves the landing screen in this render; a reload reads it from landingStore.
  const [startedNow, setStartedNow] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [localeError, setLocaleError] = useState(false);

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
    // Replies arrive while the turn is still running; the backend accepts input only once it ends, which
    // prompt.updated marks (it fires at the end of every turn, with a null prompt when nothing is asked).
    "message.appended": ({ message }) => setView((v) => v && { ...v, messages: appendMessage(v.messages, message) }),
    "prompt.updated": ({ prompt }) => {
      setView((v) => v && { ...v, prompt });
      setBusy(false);
    },
  });

  const locale = view ? sessionLocale(view.session) : null;

  // The server rendered <html lang> and the title from the browser's language; follow the session once it is known.
  useEffect(() => {
    if (!locale) return;
    document.documentElement.lang = locale;
    document.title = `${MESSAGES[locale].customer.title} · Cover Assistant`;
  }, [locale]);

  async function submit(body: InputBody) {
    await customerApi.sendInput(body);
    if (body.type === "NEEDS" && view) landingStore.clearInterest(view.session.session_id);
    setBusy(true);
  }

  function start(interest: string) {
    if (view) landingStore.start(view.session.session_id, interest);
    setStartedNow(true);
  }

  /** Optimistic: switch the UI at once, keep the server's answer, go back if the change fails. */
  async function changeLocale(next: Locale) {
    if (!view || !locale) return;
    const previous = view.session;
    setLocaleError(false);
    setSwitching(true);
    setView((v) => v && { ...v, session: { ...v.session, locale: next } });
    try {
      const session = await customerApi.setLocale(next);
      setView((v) => v && { ...v, session });
    } catch {
      setView((v) => v && { ...v, session: previous });
      setLocaleError(true);
    } finally {
      setSwitching(false);
    }
  }

  // Before the session loads, the root provider's language (Accept-Language) applies.
  if (error) return <CustomerError kind={error} />;
  if (!view || !locale) return <CustomerLoading />;

  return (
    <NextIntlClientProvider locale={locale} messages={MESSAGES[locale]}>
      <CustomerSession
        view={view}
        locale={locale}
        busy={busy}
        reconnecting={stream === "reconnecting"}
        showLanding={shouldShowLanding(
          view,
          // Only reached after the session loads on the client, so reading sessionStorage is hydration-safe.
          startedNow || landingStore.started(view.session.session_id),
        )}
        switching={switching}
        localeError={localeError}
        onStart={start}
        onSubmit={submit}
        onLocale={changeLocale}
      />
    </NextIntlClientProvider>
  );
}

function CustomerError({ kind }: { kind: "expired" | "loadFailed" }) {
  const t = useTranslations("customer");
  return (
    <main className="customer customer--center">
      <div className="notice">
        <h1>{t("errorTitle")}</h1>
        <p>{t(kind)}</p>
        {kind === "expired" && (
          <>
            <p>{t("expiredHint")}</p>
            <Link className="btn btn--primary" href="/">
              {t("startNew")}
            </Link>
          </>
        )}
      </div>
    </main>
  );
}

function CustomerLoading() {
  const t = useTranslations("common");
  return (
    <main className="customer customer--center" aria-busy>
      <span className="spinner" aria-label={t("loading")} />
    </main>
  );
}

function CustomerSession({
  view,
  locale,
  busy,
  reconnecting,
  showLanding,
  switching,
  localeError,
  onStart,
  onSubmit,
  onLocale,
}: {
  view: SessionView;
  locale: Locale;
  busy: boolean;
  reconnecting: boolean;
  showLanding: boolean;
  switching: boolean;
  localeError: boolean;
  onStart: (interest: string) => void;
  onSubmit: (body: InputBody) => Promise<void>;
  onLocale: (locale: Locale) => void;
}) {
  const t = useTranslations();
  const { session, messages, prompt } = view;
  const localeSwitch = <LocaleSwitch value={locale} onChange={onLocale} disabled={switching} />;
  const localeNotice = localeError && (
    <p className="locale-error" role="alert">
      {t("customer.localeFailed")}
    </p>
  );

  if (showLanding) {
    return <Landing market={session.market} onStart={onStart} localeSwitch={localeSwitch} notice={localeNotice} />;
  }
  const lastBotText = [...messages].reverse().find((m) => m.role !== "customer")?.text;

  return (
    <main className="customer customer--chat">
      <header className="customer__header">
        <div className="brand">
          <span className="brand__mark" aria-hidden>
            ◆
          </span>
          <div>
            <strong>{t("common.appName")}</strong>
            <span className="brand__sub">{t("customer.sub", { market: session.market })}</span>
          </div>
        </div>
        <StageStrip stage={session.stage} compact />
        <div className="customer__tools">
          {reconnecting && <span className="conn">{t("common.reconnecting")}</span>}
          {localeSwitch}
        </div>
      </header>
      {localeNotice}
      <section className="customer__chat">
        <MessageList messages={messages} perspective="customer" busy={busy} />
      </section>
      <footer className="customer__input">
        <InputPanel
          actor="customer"
          session={session}
          prompt={prompt}
          busy={busy}
          onSubmit={onSubmit}
          showPromptMessage={!!prompt?.message && prompt.message !== lastBotText}
          needsDraft={landingStore.interest(session.session_id)}
        />
      </footer>
    </main>
  );
}
