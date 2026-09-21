"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import type { Market } from "@/lib/types";
import { landingProducts, type ProductIcon } from "./copy";

const STEPS = ["verify", "questions", "recommend", "apply"] as const;

/**
 * First screen of /s/{token}: what the assistant does, the four steps, and a chat-style box to start.
 * Whatever the customer types or picks here is sent as their INTAKE answer (see lib/landing.ts).
 */
export function Landing({
  market,
  onStart,
  localeSwitch,
  notice,
}: {
  market: Market;
  onStart: (interest: string) => void;
  localeSwitch?: React.ReactNode;
  notice?: React.ReactNode;
}) {
  const t = useTranslations("customer");
  const tp = useTranslations(`products.${market}`);
  const tc = useTranslations("common");
  const products = landingProducts(market);
  const [text, setText] = useState("");

  function submit() {
    onStart(text.trim());
  }

  return (
    <div className="landing">
      <header className="landing__nav">
        <div className="landing__logo">
          <span className="landing__mark" aria-hidden>
            ◆
          </span>
          {tc("appName")}
        </div>
        <div className="landing__tools">
          <span className="landing__market">{t("sub", { market })}</span>
          {localeSwitch}
        </div>
      </header>
      {notice}

      <section className="landing__hero">
        <div className="landing__intro">
          <p className="landing__eyebrow">{t("eyebrow")}</p>
          <h1 className="landing__headline">
            {t("headline1")}
            <br />
            {t("headline2")}
          </h1>
          <p className="landing__lede">{t("lede")}</p>

          <form
            className="ask"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <textarea
              className="ask__input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={t("placeholder")}
              rows={2}
              aria-label={t("placeholder")}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
            <div className="ask__bar">
              <button type="button" className="ask__plain" onClick={() => onStart("")}>
                {t("startPlain")}
              </button>
              <button className="ask__send" aria-label={t("start")} title={t("start")}>
                <Arrow />
              </button>
            </div>
          </form>
        </div>

        <ul className="bento">
          {products.map((p, i) => (
            <li key={p.key} className={`bento__item ${i < 2 ? "bento__item--big" : ""}`}>
              <button className={`product product--${p.icon}`} onClick={() => onStart(tp(`${p.key}.ask`))}>
                <span className="product__text">
                  <span className="product__name">
                    {tp(`${p.key}.name`)}
                    {p.badge && <span className={`product__badge product__badge--${p.badge.toLowerCase()}`}>{p.badge}</span>}
                  </span>
                  <span className="product__blurb">{tp(`${p.key}.blurb`)}</span>
                  {i < 2 && (
                    <span className="product__go">
                      {t("go")} <span aria-hidden>↗</span>
                    </span>
                  )}
                </span>
                <span className="product__art" aria-hidden>
                  <Icon name={p.icon} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="steps" aria-labelledby="steps-title">
        <div className="steps__head">
          <h2 id="steps-title">{t("stepsTitle")}</h2>
          <span className="steps__time">{t("duration")}</span>
        </div>
        <ol className="steps__list">
          {STEPS.map((s, i) => (
            <li key={s} className="steps__item">
              <span className="steps__num">{i + 1}</span>
              <strong>{t(`steps.${s}.title`)}</strong>
              <span>{t(`steps.${s}.body`)}</span>
            </li>
          ))}
        </ol>
      </section>

      <footer className="landing__foot">{t("privacy")}</footer>
    </div>
  );
}

function Arrow() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 16V4M5 9l5-5 5 5" />
    </svg>
  );
}

function Icon({ name }: { name: ProductIcon }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;
  return (
    <svg viewBox="0 0 48 48" width="100%" height="100%">
      {name === "plane" && (
        <path {...common} d="M6 27l8 2 7-5-9-12 4-1 13 10 7-5c2-1 4-1 5 0s0 3-1 4l-17 13-4 1-3-4-6 1z" />
      )}
      {name === "phone" && (
        <>
          <rect {...common} x="14" y="5" width="20" height="38" rx="4" />
          <path {...common} d="M21 38h6M19 15l4 4 7-7" />
        </>
      )}
      {name === "laptop" && (
        <>
          <rect {...common} x="9" y="11" width="30" height="20" rx="2" />
          <path {...common} d="M4 36h40l-3 4H7zM20 21l3 3 6-6" />
        </>
      )}
      {name === "appliance" && (
        <>
          <rect {...common} x="7" y="9" width="34" height="23" rx="2" />
          <path {...common} d="M18 39h12M24 32v7M20 20l3 3 6-6" />
        </>
      )}
    </svg>
  );
}
