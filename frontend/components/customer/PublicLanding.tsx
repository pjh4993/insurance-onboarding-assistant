"use client";

import { NextIntlClientProvider, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { localeMarket, type Locale } from "@/i18n/locales";
import { MESSAGES } from "@/i18n/messages";
import { ApiError, publicApi } from "@/lib/api";
import { landingStore } from "@/lib/landing";
import { retryMinutes } from "@/lib/start";
import type { Market } from "@/lib/types";
import { LocaleSwitch } from "../LocaleSwitch";
import { Landing } from "./Landing";
import { MarketSwitch } from "./MarketSwitch";

type StartError = { kind: "rateLimited"; minutes: number | null } | { kind: "failed" };

/**
 * The public landing page (/): the session-link Landing, for anyone. Starting creates a session through
 * /api/start (which sets the httpOnly session cookie), remembers what the visitor typed or picked for the
 * first profiling answer (lib/landing.ts), and opens the chat at /chat.
 */
export function PublicLanding({
  initialLocale,
  resumable,
  agentHref,
}: {
  initialLocale: Locale;
  /** The session cookie names a session that has not ended: offer to continue it. */
  resumable: boolean;
  agentHref: string;
}) {
  const router = useRouter();
  const [locale, setLocale] = useState<Locale>(initialLocale);
  // null = follow the language (ko → KR, en → US) until the visitor picks a market.
  const [pickedMarket, setPickedMarket] = useState<Market | null>(null);
  const market = pickedMarket ?? localeMarket(locale);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<StartError | null>(null);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  async function start(interest: string) {
    if (starting) return;
    setStarting(true);
    setError(null);
    try {
      const { session_id } = await publicApi.start(market, locale);
      // Marks the new session as started, so /chat skips its own landing screen and pre-fills NEEDS.
      landingStore.start(session_id, interest);
      router.push("/chat");
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 429 ? { kind: "rateLimited", minutes: retryMinutes(e.retryAfter) } : { kind: "failed" },
      );
      setStarting(false);
    }
  }

  return (
    <NextIntlClientProvider locale={locale} messages={MESSAGES[locale]}>
      <div className={`public-landing ${starting ? "public-landing--busy" : ""}`} aria-busy={starting}>
        <Landing
          market={market}
          onStart={start}
          localeSwitch={
            <>
              <MarketSwitch value={market} onChange={setPickedMarket} disabled={starting} />
              <LocaleSwitch value={locale} onChange={setLocale} disabled={starting} />
            </>
          }
          notice={<Notices error={error} resumable={resumable} onStartNew={() => start("")} />}
        />
        <AgentsLink href={agentHref} />
      </div>
    </NextIntlClientProvider>
  );
}

function Notices({ error, resumable, onStartNew }: { error: StartError | null; resumable: boolean; onStartNew: () => void }) {
  const t = useTranslations("home");
  if (!error && !resumable) return null;
  return (
    <div className="landing-notices">
      {error && (
        <p className="landing-notice landing-notice--error" role="alert">
          {error.kind === "failed"
            ? t("startFailed")
            : error.minutes === null
              ? t("rateLimitedLater")
              : t("rateLimited", { minutes: error.minutes })}
        </p>
      )}
      {resumable && (
        <div className="landing-notice" role="status">
          <span>{t("resumeBody")}</span>
          <span className="landing-notice__actions">
            <Link className="landing-notice__go" href="/chat">
              {t("resumeContinue")}
            </Link>
            <button type="button" className="landing-notice__alt" onClick={onStartNew}>
              {t("resumeStartNew")}
            </button>
          </span>
        </div>
      )}
    </div>
  );
}

function AgentsLink({ href }: { href: string }) {
  const t = useTranslations("home");
  return (
    <p className="public-landing__agents">
      {/* A plain link: the console may be on another host, and it is a separate app either way. */}
      <a href={href}>{t("forAgents")}</a>
    </p>
  );
}
