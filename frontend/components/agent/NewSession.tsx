"use client";

import { useState } from "react";
import { agentApi, ApiError } from "@/lib/api";
import type { Market } from "@/lib/types";

export function NewSession({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [market, setMarket] = useState<Market>("KR");
  const [creating, setCreating] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function create() {
    setCreating(true);
    setError(null);
    setCopied(false);
    try {
      const res = await agentApi.createSession(market);
      setLink(`${window.location.origin}${res.customer_path}`);
      onCreated();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create a session");
    } finally {
      setCreating(false);
    }
  }

  if (!open) {
    return (
      <button className="btn btn--primary btn--block" onClick={() => setOpen(true)}>
        + New session
      </button>
    );
  }
  return (
    <div className="new-session">
      <div className="row row--between">
        <strong>New customer session</strong>
        <button
          className="btn btn--link"
          onClick={() => {
            setOpen(false);
            setLink(null);
          }}
        >
          Close
        </button>
      </div>
      <div className="segmented" role="radiogroup" aria-label="Market">
        {(["KR", "US"] as const).map((m) => (
          <button
            key={m}
            role="radio"
            aria-checked={market === m}
            className={market === m ? "is-on" : ""}
            onClick={() => setMarket(m)}
          >
            {m === "KR" ? "Korea (KR)" : "United States (US)"}
          </button>
        ))}
      </div>
      <button className="btn btn--primary btn--block" onClick={create} disabled={creating}>
        {creating ? "Creating…" : "Create link"}
      </button>
      {error && <p className="input-panel__error">{error}</p>}
      {link && (
        <div className="link-box">
          <span className="muted">Customer link</span>
          <code>{link}</code>
          <div className="row">
            <button
              className="btn btn--ghost"
              onClick={() => {
                void navigator.clipboard?.writeText(link).then(() => setCopied(true));
              }}
            >
              {copied ? "Copied" : "Copy"}
            </button>
            <a className="btn btn--ghost" href={link} target="_blank" rel="noreferrer">
              Open ↗
            </a>
          </div>
          <p className="hint">Open it in a private window to keep the customer cookie separate.</p>
        </div>
      )}
    </div>
  );
}
