"use client";

import { useState, type FormEvent } from "react";
import type { InputBody, Market, RecommendationCard } from "@/lib/types";
import { RecommendationCardView } from "../RecommendationCardView";

/** Resolves true when the backend accepted the input; the caller shows any error. */
export type Submit = (body: InputBody) => Promise<boolean>;

const ID_TYPES: Record<Market, { value: string; label: string }[]> = {
  KR: [
    { value: "NATIONAL_ID", label: "Resident registration card" },
    { value: "DRIVER_LICENSE", label: "Driver's license" },
    { value: "PASSPORT", label: "Passport" },
  ],
  US: [
    { value: "DRIVER_LICENSE", label: "Driver's license" },
    { value: "PASSPORT", label: "Passport" },
    { value: "NATIONAL_ID", label: "State ID" },
  ],
};

export function IdentityForm({ market, onSubmit, disabled }: { market: Market; onSubmit: Submit; disabled: boolean }) {
  const [consent, setConsent] = useState(false);

  async function handle(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "").trim();
    await onSubmit({
      type: "IDENTITY_INFO",
      data: {
        full_name: get("full_name"),
        email: get("email"),
        phone: get("phone"),
        id_document_type: get("id_document_type"),
        id_document_number: get("id_document_number"),
        third_party_consent: consent,
      },
    });
  }

  return (
    <form className="form" onSubmit={handle} autoComplete="on">
      <div className="form__grid">
        <label className="field field--wide">
          <span>Full name</span>
          <input name="full_name" required autoComplete="name" />
        </label>
        <label className="field">
          <span>Email</span>
          <input name="email" type="email" required autoComplete="email" />
        </label>
        <label className="field">
          <span>Mobile phone</span>
          <input
            name="phone"
            type="tel"
            required
            autoComplete="tel"
            placeholder={market === "KR" ? "+821012345678" : "+12065550100"}
          />
        </label>
        <label className="field">
          <span>ID type</span>
          <select name="id_document_type" required defaultValue={ID_TYPES[market][0].value}>
            {ID_TYPES[market].map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>ID number</span>
          <input name="id_document_number" required autoComplete="off" spellCheck={false} />
        </label>
      </div>
      <label className="check">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>
          I agree that my details may be checked with the retail partner I bought from, so my purchase can be
          pre-filled. <em>Optional — without it we verify you by SMS code.</em>
        </span>
      </label>
      <div className="form__actions">
        <button className="btn btn--primary" disabled={disabled}>
          Verify my identity
        </button>
      </div>
    </form>
  );
}

export function OtpForm({ onSubmit, disabled }: { onSubmit: Submit; disabled: boolean }) {
  const [code, setCode] = useState("");
  return (
    <form
      className="form form--inline"
      onSubmit={async (e) => {
        e.preventDefault();
        if (await onSubmit({ type: "OTP_CODE", data: { code: code.trim() } })) setCode("");
      }}
    >
      <label className="field">
        <span>Verification code</span>
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 8))}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="6-digit code"
          className="otp"
          required
          minLength={4}
        />
      </label>
      <button className="btn btn--primary" disabled={disabled || code.length < 4}>
        Verify
      </button>
    </form>
  );
}

export function TextComposer({
  onSend,
  disabled,
  placeholder,
  cta = "Send",
}: {
  onSend: (text: string) => Promise<boolean>;
  disabled: boolean;
  placeholder: string;
  cta?: string;
}) {
  const [text, setText] = useState("");
  async function send() {
    const t = text.trim();
    if (!t) return;
    if (await onSend(t)) setText("");
  }
  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        void send();
      }}
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        rows={2}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            void send();
          }
        }}
      />
      <button className="btn btn--primary" disabled={disabled || !text.trim()}>
        {cta}
      </button>
    </form>
  );
}

export function DecisionPanel({
  options,
  onSubmit,
  disabled,
}: {
  options: RecommendationCard[];
  onSubmit: Submit;
  disabled: boolean;
}) {
  const [mode, setMode] = useState<"choose" | "change" | "decline">("choose");
  const sorted = [...options].sort((a, b) => {
    const ea = a.eligibility_result === "ELIGIBLE" ? 0 : 1;
    const eb = b.eligibility_result === "ELIGIBLE" ? 0 : 1;
    return ea - eb || a.rank - b.rank;
  });
  const anyEligible = sorted.some((o) => o.eligibility_result === "ELIGIBLE");

  return (
    <div className="decision">
      <div className="rec-grid">
        {sorted.map((card) => (
          <RecommendationCardView
            key={card.recommendation_id}
            card={card}
            actions={
              card.eligibility_result === "ELIGIBLE" && card.status === "PROPOSED" ? (
                <button
                  className="btn btn--primary btn--block"
                  disabled={disabled}
                  onClick={() =>
                    onSubmit({
                      type: "DECISION",
                      data: { decision: "ACCEPT", recommendation_id: card.recommendation_id },
                    })
                  }
                >
                  Accept this plan
                </button>
              ) : undefined
            }
          />
        ))}
        {sorted.length === 0 && <p className="muted">No products to show.</p>}
      </div>

      {mode === "choose" && (
        <div className="decision__alt">
          {!anyEligible && <p className="muted">None of the products fit right now.</p>}
          <button className="btn btn--ghost" disabled={disabled} onClick={() => setMode("change")}>
            Change my answers
          </button>
          <button className="btn btn--ghost btn--danger" disabled={disabled} onClick={() => setMode("decline")}>
            Decline
          </button>
        </div>
      )}
      {mode === "change" && (
        <div className="decision__followup">
          <TextComposer
            disabled={disabled}
            placeholder="What changed? e.g. “The trip is 10 days, not 5.”"
            cta="Update"
            onSend={(text) => onSubmit({ type: "DECISION", data: { decision: "CHANGE", text } })}
          />
          <button className="btn btn--link" onClick={() => setMode("choose")}>
            Back
          </button>
        </div>
      )}
      {mode === "decline" && (
        <div className="decision__followup">
          <p className="muted">Decline all offers? You can tell us why (optional).</p>
          <div className="row">
            <button
              className="btn btn--danger"
              disabled={disabled}
              onClick={() => onSubmit({ type: "DECISION", data: { decision: "DECLINE" } })}
            >
              Decline all offers
            </button>
            <button className="btn btn--link" onClick={() => setMode("choose")}>
              Back
            </button>
          </div>
          <TextComposer
            disabled={disabled}
            placeholder="Reason (optional)"
            cta="Decline with reason"
            onSend={(text) => onSubmit({ type: "DECISION", data: { decision: "DECLINE", text } })}
          />
        </div>
      )}
    </div>
  );
}

export function ConfirmPanel({
  summary,
  onSubmit,
  disabled,
}: {
  summary?: string;
  onSubmit: Submit;
  disabled: boolean;
}) {
  const [fixing, setFixing] = useState(false);
  return (
    <div className="confirm">
      <div className="confirm__summary">
        <h4>Application summary</h4>
        <p>{summary?.trim() || "Please review the details above."}</p>
      </div>
      {fixing ? (
        <div className="decision__followup">
          <TextComposer
            disabled={disabled}
            placeholder="What should we fix? e.g. “The payer is my spouse, Kim Minji.”"
            cta="Send fix"
            onSend={(text) => onSubmit({ type: "CONFIRM", data: { confirmed: false, text } })}
          />
          <button className="btn btn--link" onClick={() => setFixing(false)}>
            Back
          </button>
        </div>
      ) : (
        <div className="row">
          <button
            className="btn btn--primary"
            disabled={disabled}
            onClick={() => onSubmit({ type: "CONFIRM", data: { confirmed: true } })}
          >
            Confirm and submit
          </button>
          <button className="btn btn--ghost" disabled={disabled} onClick={() => setFixing(true)}>
            Fix something
          </button>
        </div>
      )}
    </div>
  );
}

export function HandoffPanel({ onSubmit, disabled }: { onSubmit: Submit; disabled: boolean }) {
  const [note, setNote] = useState("");
  const send = (resolution: "VERIFIED" | "CONTINUE" | "END") =>
    onSubmit({ type: "AGENT", data: { resolution, ...(note.trim() ? { note: note.trim() } : {}) } });
  return (
    <div className="handoff">
      <p className="handoff__title">Handoff — resolve to hand the session back to the flow</p>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        placeholder="Note (optional) — e.g. “Verified by video call, passport checked.”"
      />
      <div className="row">
        <button className="btn btn--success" disabled={disabled} onClick={() => send("VERIFIED")}>
          Verified
        </button>
        <button className="btn btn--primary" disabled={disabled} onClick={() => send("CONTINUE")}>
          Continue
        </button>
        <button className="btn btn--danger" disabled={disabled} onClick={() => send("END")}>
          End session
        </button>
      </div>
    </div>
  );
}
