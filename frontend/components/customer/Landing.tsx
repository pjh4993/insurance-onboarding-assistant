"use client";

import { useState } from "react";
import type { Market } from "@/lib/types";
import { customerCopy, landingProducts, type ProductIcon } from "./copy";

/**
 * First screen of /s/{token}: what the assistant does, the four steps, and a chat-style box to start.
 * Whatever the customer types or picks here becomes their first profiling answer (see lib/landing.ts).
 */
export function Landing({ market, onStart }: { market: Market; onStart: (interest: string) => void }) {
  const c = customerCopy(market);
  const products = landingProducts(market);
  const [text, setText] = useState("");

  function submit() {
    onStart(text.trim());
  }

  return (
    <div className="landing" lang={c.lang}>
      <header className="landing__nav">
        <div className="landing__logo">
          <span className="landing__mark" aria-hidden>
            ◆
          </span>
          Cover Assistant
        </div>
        <span className="landing__market">{c.sub(market)}</span>
      </header>

      <section className="landing__hero">
        <div className="landing__intro">
          <p className="landing__eyebrow">{c.eyebrow}</p>
          <h1 className="landing__headline">
            {c.headline[0]}
            <br />
            {c.headline[1]}
          </h1>
          <p className="landing__lede">{c.lede}</p>

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
              placeholder={c.placeholder}
              rows={2}
              aria-label={c.placeholder}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
            <div className="ask__bar">
              <button type="button" className="ask__plain" onClick={() => onStart("")}>
                {c.startPlain}
              </button>
              <button className="ask__send" aria-label={c.start} title={c.start}>
                <Arrow />
              </button>
            </div>
          </form>
        </div>

        <ul className="bento">
          {products.map((p, i) => (
            <li key={p.name} className={`bento__item ${i < 2 ? "bento__item--big" : ""}`}>
              <button className={`product product--${p.icon}`} onClick={() => onStart(p.ask)}>
                <span className="product__text">
                  <span className="product__name">
                    {p.name}
                    {p.badge && <span className={`product__badge product__badge--${p.badge.toLowerCase()}`}>{p.badge}</span>}
                  </span>
                  <span className="product__blurb">{p.blurb}</span>
                  {i < 2 && (
                    <span className="product__go">
                      {c.go} <span aria-hidden>↗</span>
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
          <h2 id="steps-title">{c.stepsTitle}</h2>
          <span className="steps__time">{c.duration}</span>
        </div>
        <ol className="steps__list">
          {c.steps.map((s, i) => (
            <li key={s.title} className="steps__item">
              <span className="steps__num">{i + 1}</span>
              <strong>{s.title}</strong>
              <span>{s.body}</span>
            </li>
          ))}
        </ol>
      </section>

      <footer className="landing__foot">{c.privacy}</footer>
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
