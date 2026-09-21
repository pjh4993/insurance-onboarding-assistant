"use client";

import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";
import type { InputBody, Market, RecommendationCard } from "@/lib/types";
import { RecommendationCardView } from "../RecommendationCardView";

/** Resolves true when the backend accepted the input; the caller shows any error. */
export type Submit = (body: InputBody) => Promise<boolean>;

// Order per market; labels are in messages (idType.<market>.<type>).
const ID_TYPES: Record<Market, ("NATIONAL_ID" | "DRIVER_LICENSE" | "PASSPORT")[]> = {
  KR: ["NATIONAL_ID", "DRIVER_LICENSE", "PASSPORT"],
  US: ["DRIVER_LICENSE", "PASSPORT", "NATIONAL_ID"],
};

export function IdentityForm({ market, onSubmit, disabled }: { market: Market; onSubmit: Submit; disabled: boolean }) {
  const t = useTranslations();
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
          <span>{t("identity.fullName")}</span>
          <input name="full_name" required autoComplete="name" />
        </label>
        <label className="field">
          <span>{t("identity.email")}</span>
          <input name="email" type="email" required autoComplete="email" />
        </label>
        <label className="field">
          <span>{t("identity.phone")}</span>
          <input
            name="phone"
            type="tel"
            required
            autoComplete="tel"
            placeholder={market === "KR" ? "+821012345678" : "+12065550100"}
          />
        </label>
        <label className="field">
          <span>{t("identity.idType")}</span>
          <select name="id_document_type" required defaultValue={ID_TYPES[market][0]}>
            {ID_TYPES[market].map((type) => (
              <option key={type} value={type}>
                {t(`idType.${market}.${type}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("identity.idNumber")}</span>
          <input name="id_document_number" required autoComplete="off" spellCheck={false} />
        </label>
      </div>
      <label className="check">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>
          {t("identity.consent")} <em>{t("identity.consentNote")}</em>
        </span>
      </label>
      <div className="form__actions">
        <button className="btn btn--primary" disabled={disabled}>
          {t("identity.submit")}
        </button>
      </div>
    </form>
  );
}

export function OtpForm({ onSubmit, disabled }: { onSubmit: Submit; disabled: boolean }) {
  const t = useTranslations("otp");
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
        <span>{t("label")}</span>
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 8))}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder={t("placeholder")}
          className="otp"
          required
          minLength={4}
        />
      </label>
      <button className="btn btn--primary" disabled={disabled || code.length < 4}>
        {t("submit")}
      </button>
    </form>
  );
}

export function TextComposer({
  onSend,
  disabled,
  placeholder,
  cta,
  initialText = "",
}: {
  onSend: (text: string) => Promise<boolean>;
  disabled: boolean;
  placeholder: string;
  cta?: string;
  initialText?: string;
}) {
  const t = useTranslations("input");
  const [text, setText] = useState(initialText);
  async function send() {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (await onSend(trimmed)) setText("");
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
        {cta ?? t("send")}
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
  const t = useTranslations();
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
                  {t("decision.accept")}
                </button>
              ) : undefined
            }
          />
        ))}
        {sorted.length === 0 && <p className="muted">{t("decision.noProducts")}</p>}
      </div>

      {mode === "choose" && (
        <div className="decision__alt">
          {!anyEligible && <p className="muted">{t("decision.noneFit")}</p>}
          <button className="btn btn--ghost" disabled={disabled} onClick={() => setMode("change")}>
            {t("decision.change")}
          </button>
          <button className="btn btn--ghost btn--danger" disabled={disabled} onClick={() => setMode("decline")}>
            {t("decision.decline")}
          </button>
        </div>
      )}
      {mode === "change" && (
        <div className="decision__followup">
          <TextComposer
            disabled={disabled}
            placeholder={t("decision.changePlaceholder")}
            cta={t("decision.update")}
            onSend={(text) => onSubmit({ type: "DECISION", data: { decision: "CHANGE", text } })}
          />
          <button className="btn btn--link" onClick={() => setMode("choose")}>
            {t("common.back")}
          </button>
        </div>
      )}
      {mode === "decline" && (
        <div className="decision__followup">
          <p className="muted">{t("decision.declineAsk")}</p>
          <div className="row">
            <button
              className="btn btn--danger"
              disabled={disabled}
              onClick={() => onSubmit({ type: "DECISION", data: { decision: "DECLINE" } })}
            >
              {t("decision.declineAll")}
            </button>
            <button className="btn btn--link" onClick={() => setMode("choose")}>
              {t("common.back")}
            </button>
          </div>
          <TextComposer
            disabled={disabled}
            placeholder={t("decision.reasonPlaceholder")}
            cta={t("decision.declineWithReason")}
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
  const t = useTranslations();
  const [fixing, setFixing] = useState(false);
  return (
    <div className="confirm">
      <div className="confirm__summary">
        <h4>{t("confirm.title")}</h4>
        <p>{summary?.trim() || t("confirm.fallback")}</p>
      </div>
      {fixing ? (
        <div className="decision__followup">
          <TextComposer
            disabled={disabled}
            placeholder={t("confirm.fixPlaceholder")}
            cta={t("confirm.sendFix")}
            onSend={(text) => onSubmit({ type: "CONFIRM", data: { confirmed: false, text } })}
          />
          <button className="btn btn--link" onClick={() => setFixing(false)}>
            {t("common.back")}
          </button>
        </div>
      ) : (
        <div className="row">
          <button
            className="btn btn--primary"
            disabled={disabled}
            onClick={() => onSubmit({ type: "CONFIRM", data: { confirmed: true } })}
          >
            {t("confirm.submit")}
          </button>
          <button className="btn btn--ghost" disabled={disabled} onClick={() => setFixing(true)}>
            {t("confirm.fix")}
          </button>
        </div>
      )}
    </div>
  );
}

export function HandoffPanel({ onSubmit, disabled }: { onSubmit: Submit; disabled: boolean }) {
  const t = useTranslations("handoff");
  const [note, setNote] = useState("");
  const send = (resolution: "VERIFIED" | "CONTINUE" | "END") =>
    onSubmit({ type: "AGENT", data: { resolution, ...(note.trim() ? { note: note.trim() } : {}) } });
  return (
    <div className="handoff">
      <p className="handoff__title">{t("title")}</p>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        placeholder={t("notePlaceholder")}
      />
      <div className="row">
        <button className="btn btn--success" disabled={disabled} onClick={() => send("VERIFIED")}>
          {t("verified")}
        </button>
        <button className="btn btn--primary" disabled={disabled} onClick={() => send("CONTINUE")}>
          {t("continue")}
        </button>
        <button className="btn btn--danger" disabled={disabled} onClick={() => send("END")}>
          {t("end")}
        </button>
      </div>
    </div>
  );
}
