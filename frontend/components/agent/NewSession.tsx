"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { LOCALES, marketLocale } from "@/i18n/locales";
import { agentApi, ApiError } from "@/lib/api";
import type { Locale, Market } from "@/lib/types";

export function NewSession({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const t = useTranslations("agent.newSession");
  const tc = useTranslations("common");
  const [market, setMarket] = useState<Market>("KR");
  // null = the market's default language (the backend picks it); otherwise sent explicitly.
  const [locale, setLocale] = useState<Locale | null>(null);
  const [creating, setCreating] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function create() {
    setCreating(true);
    setError(null);
    setCopied(false);
    try {
      const res = await agentApi.createSession(market, locale ?? undefined);
      setLink(`${window.location.origin}${res.customer_path}`);
      onCreated();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("createFailed"));
    } finally {
      setCreating(false);
    }
  }

  if (!open) {
    return (
      <button className="btn btn--primary btn--block" onClick={() => setOpen(true)}>
        {t("open")}
      </button>
    );
  }
  return (
    <div className="new-session">
      <div className="row row--between">
        <strong>{t("title")}</strong>
        <button
          className="btn btn--link"
          onClick={() => {
            setOpen(false);
            setLink(null);
          }}
        >
          {tc("close")}
        </button>
      </div>
      <div className="segmented" role="radiogroup" aria-label={t("market")}>
        {(["KR", "US"] as const).map((m) => (
          <button
            key={m}
            role="radio"
            aria-checked={market === m}
            className={market === m ? "is-on" : ""}
            onClick={() => setMarket(m)}
          >
            {t(`marketName.${m}`)}
          </button>
        ))}
      </div>
      <div className="segmented segmented--3" role="radiogroup" aria-label={t("language")}>
        <button role="radio" aria-checked={locale === null} className={locale === null ? "is-on" : ""} onClick={() => setLocale(null)}>
          {t("languageAuto")} · {tc(`localeShort.${marketLocale(market)}`)}
        </button>
        {LOCALES.map((l) => (
          <button
            key={l}
            role="radio"
            lang={l}
            aria-checked={locale === l}
            className={locale === l ? "is-on" : ""}
            onClick={() => setLocale(l)}
          >
            {tc(`localeName.${l}`)}
          </button>
        ))}
      </div>
      <button className="btn btn--primary btn--block" onClick={create} disabled={creating}>
        {creating ? t("creating") : t("create")}
      </button>
      {error && <p className="input-panel__error">{error}</p>}
      {link && (
        <div className="link-box">
          <span className="muted">{t("link")}</span>
          <code>{link}</code>
          <div className="row">
            <button
              className="btn btn--ghost"
              onClick={() => {
                void navigator.clipboard?.writeText(link).then(() => setCopied(true));
              }}
            >
              {copied ? t("copied") : t("copy")}
            </button>
            <a className="btn btn--ghost" href={link} target="_blank" rel="noreferrer">
              {t("openLink")}
            </a>
          </div>
          <p className="hint">{t("hint")}</p>
        </div>
      )}
    </div>
  );
}
