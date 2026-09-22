"use client";

import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import {
  answerSummary,
  buildTopicAnswer,
  firstOpenField,
  initialFormState,
  validateField,
  validateForm,
  type FieldError,
  type FormState,
} from "@/lib/topicForm";
import type { FormField, FormSpec } from "@/lib/types";
import { TextComposer, type Submit } from "./forms";

/**
 * A small topic form from `prompt.form` (IDENTITY_INFO or NEEDS). With `stepped` (the customer chat) it asks
 * one field at a time: answered fields collect above the current question, each with an edit button, and
 * the button sends the whole form after the last one. Without it (the agent console) every field shows at
 * once. With `allow_text` on a NEEDS prompt, a free-text composer sits under it as well. Remount it (key)
 * when the prompt's form changes.
 */
export function TopicForm({
  form,
  type,
  onSubmit,
  disabled,
  textPlaceholder,
  stepped = false,
}: {
  form: FormSpec;
  type: "IDENTITY_INFO" | "NEEDS";
  onSubmit: Submit;
  disabled: boolean;
  textPlaceholder: string;
  stepped?: boolean;
}) {
  const t = useTranslations("topicForm");
  const id = useId();
  const [state, setState] = useState<FormState>(() => initialFormState(form));
  const [errors, setErrors] = useState<Record<string, FieldError>>({});
  const [step, setStep] = useState(() => (stepped ? firstOpenField(form, state) : 0));
  // Focus follows the question only after the customer moved it, so opening the form does not grab focus.
  const moved = useRef(false);
  // IDENTITY_INFO takes form answers only (contract); free text is a NEEDS answer.
  const allowText = form.allow_text && type === "NEEDS";
  const last = form.fields.length - 1;
  const current = form.fields[step];

  useEffect(() => {
    if (stepped && moved.current && current) document.getElementById(`${id}-${current.name}`)?.focus();
  }, [stepped, step, id, current]);

  function set(name: string, value: FormState[string]) {
    setState((s) => ({ ...s, [name]: value }));
    setErrors((e) => {
      if (!(name in e)) return e;
      const next = { ...e };
      delete next[name];
      return next;
    });
  }

  function goTo(i: number) {
    moved.current = true;
    setStep(i);
  }

  async function send(values: FormState) {
    const found = validateForm(form, values);
    setErrors(found);
    const first = form.fields.findIndex((f) => found[f.name]);
    if (first >= 0) {
      if (stepped) goTo(first);
      else document.getElementById(`${id}-${form.fields[first].name}`)?.focus();
      return;
    }
    await onSubmit({ type, data: buildTopicAnswer(form, values) });
  }

  // The current question is answered: check it, then move on (or send after the last one).
  async function advance(values: FormState) {
    const error = validateField(current, values[current.name]);
    if (error) {
      setErrors((e) => ({ ...e, [current.name]: error }));
      document.getElementById(`${id}-${current.name}`)?.focus();
      return;
    }
    if (step < last) goTo(step + 1);
    else await send(values);
  }

  async function handle(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (stepped) await advance(state);
    else await send(state);
  }

  const titleId = `${id}-title`;
  const yesNo = { yes: t("yes"), no: t("no") };

  if (stepped && current) {
    const value = state[current.name];
    const empty = !current.required && current.kind !== "boolean" && answerSummary(current, value, yesNo) === "";
    return (
      <div className="topic-form topic-form--stepped">
        <form className="stepper" data-type={type} onSubmit={handle} noValidate aria-labelledby={titleId}>
          <div className="stepper__head">
            <div className="stepper__progress" aria-hidden>
              {form.fields.map((f, i) => (
                <span key={f.name} className={i < step ? "done" : i === step ? "now" : undefined} />
              ))}
            </div>
            <p className="stepper__topic" id={titleId}>
              {t("progress", { title: form.title, step: step + 1, total: form.fields.length })}
            </p>
            {step === 0 && form.reason && <p className="stepper__reason">{form.reason}</p>}
          </div>
          {step > 0 && (
            <dl className="stepper__answered">
              {form.fields.slice(0, step).map((f, i) => (
                <div key={f.name}>
                  <dt>{f.label}</dt>
                  <dd>
                    <span>{answerSummary(f, state[f.name], yesNo) || t("skipped")}</span>
                    <button type="button" className="link-btn" disabled={disabled} onClick={() => goTo(i)}>
                      {t("edit")}
                    </button>
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <Question
            id={`${id}-${current.name}`}
            field={current}
            value={value}
            error={errors[current.name]}
            onChange={(v) => set(current.name, v)}
            onPick={(v) => {
              const values = { ...state, [current.name]: v };
              set(current.name, v);
              void advance(values);
            }}
          />
          <button className="btn btn--primary btn--cta" disabled={disabled}>
            {empty ? t("skip") : step < last ? t("next") : t("submit")}
          </button>
        </form>
        {allowText && <FreeText disabled={disabled} placeholder={textPlaceholder} onSubmit={onSubmit} />}
      </div>
    );
  }

  return (
    <div className="topic-form">
      <form className="form" onSubmit={handle} noValidate aria-labelledby={titleId}>
        <div className="topic-form__head">
          <h4 id={titleId}>{form.title}</h4>
          {form.reason && <p className="topic-form__reason">{form.reason}</p>}
        </div>
        <div className="form__grid">
          {form.fields.map((f) => (
            <Field
              key={f.name}
              id={`${id}-${f.name}`}
              field={f}
              value={state[f.name]}
              error={errors[f.name]}
              wide={form.fields.length === 1 || f.kind === "multiselect" || f.kind === "boolean"}
              onChange={(v) => set(f.name, v)}
            />
          ))}
        </div>
        <div className="form__actions">
          <button className="btn btn--primary" disabled={disabled}>
            {t("submit")}
          </button>
        </div>
      </form>
      {allowText && <FreeText disabled={disabled} placeholder={textPlaceholder} onSubmit={onSubmit} />}
    </div>
  );
}

function FreeText({ disabled, placeholder, onSubmit }: { disabled: boolean; placeholder: string; onSubmit: Submit }) {
  const t = useTranslations("topicForm");
  return (
    <div className="topic-form__text">
      <p className="topic-form__or">{t("orText")}</p>
      <TextComposer disabled={disabled} placeholder={placeholder} onSend={(text) => onSubmit({ type: "NEEDS", data: { text } })} />
    </div>
  );
}

// Choices this short read better as a list of buttons than as a dropdown; picking one moves on.
const MAX_CHOICE_BUTTONS = 6;

/** The stepped form's current question: the field's label as a heading over one large input. */
function Question({
  id,
  field: f,
  value,
  error,
  onChange,
  onPick,
}: {
  id: string;
  field: FormField;
  value: FormState[string] | undefined;
  error: FieldError | undefined;
  onChange: (v: FormState[string]) => void;
  onPick: (v: FormState[string]) => void;
}) {
  const t = useTranslations("topicForm");
  const qId = `${id}-q`;
  const errId = `${id}-error`;
  const aria = { "aria-invalid": error ? true : undefined, "aria-describedby": error ? errId : undefined };
  const heading = (
    <h4 className="stepper__question" id={qId}>
      {f.label}
      {!f.required && f.kind !== "boolean" && <span className="stepper__optional">{t("optional")}</span>}
    </h4>
  );
  const errorLine = error && (
    <span className="field__error" id={errId}>
      {t(error === "number" ? "invalidNumber" : "required")}
    </span>
  );

  if (f.kind === "select" && (f.options ?? []).length <= MAX_CHOICE_BUTTONS) {
    return (
      <div className="stepper__field" role="radiogroup" aria-labelledby={qId} data-field={f.name} {...aria}>
        {heading}
        <div className="choices">
          {(f.options ?? []).map((o, i) => (
            <button
              key={o.value}
              id={i === 0 ? id : undefined}
              type="button"
              role="radio"
              data-value={o.value}
              aria-checked={value === o.value}
              className={`choice ${value === o.value ? "choice--on" : ""}`}
              onClick={() => onPick(o.value)}
            >
              {o.label}
            </button>
          ))}
        </div>
        {errorLine}
      </div>
    );
  }

  if (f.kind === "boolean") {
    return (
      <div className="stepper__field">
        <label className={`check check--card ${value === true ? "check--on" : ""}`}>
          <input
            id={id}
            name={f.name}
            type="checkbox"
            checked={value === true}
            onChange={(e) => onChange(e.target.checked)}
            {...aria}
          />
          <span>{f.label}</span>
        </label>
        {errorLine}
      </div>
    );
  }

  return (
    <div className="stepper__field">
      {heading}
      <Field id={id} field={{ ...f, label: "" }} value={value} error={error} wide onChange={onChange} labelledBy={qId} />
    </div>
  );
}

function Field({
  id,
  field: f,
  value,
  error,
  wide,
  onChange,
  labelledBy,
}: {
  id: string;
  field: FormField;
  value: FormState[string] | undefined;
  error: FieldError | undefined;
  wide: boolean;
  onChange: (v: FormState[string]) => void;
  /** The stepped form's question heading, which stands in for the field's own label. */
  labelledBy?: string;
}) {
  const t = useTranslations("topicForm");
  const errId = `${id}-error`;
  const aria = {
    "aria-invalid": error ? true : undefined,
    "aria-describedby": error ? errId : undefined,
    "aria-labelledby": labelledBy,
  };
  const errorLine = error && (
    <span className="field__error" id={errId}>
      {t(error === "number" ? "invalidNumber" : "required")}
    </span>
  );
  const label = (
    <>
      {f.label}
      {f.required && (
        <span className="field__req" aria-hidden>
          {" "}
          *
        </span>
      )}
    </>
  );

  if (f.kind === "boolean") {
    return (
      <div className={`field field--wide ${error ? "field--invalid" : ""}`}>
        <label className="check">
          <input id={id} type="checkbox" checked={value === true} onChange={(e) => onChange(e.target.checked)} {...aria} />
          <span>{label}</span>
        </label>
        {errorLine}
      </div>
    );
  }

  if (f.kind === "multiselect") {
    const picked = Array.isArray(value) ? value : [];
    return (
      <fieldset className={`field field--wide chips ${error ? "field--invalid" : ""}`} {...aria}>
        <legend>{label}</legend>
        <div className="chips__list">
          {(f.options ?? []).map((o, i) => (
            <label key={o.value} className={`chip ${picked.includes(o.value) ? "chip--on" : ""}`}>
              <input
                id={i === 0 ? id : undefined}
                type="checkbox"
                checked={picked.includes(o.value)}
                onChange={(e) =>
                  onChange(e.target.checked ? [...picked, o.value] : picked.filter((v) => v !== o.value))
                }
              />
              <span>{o.label}</span>
            </label>
          ))}
        </div>
        {errorLine}
      </fieldset>
    );
  }

  const text = typeof value === "string" ? value : "";
  return (
    <label className={`field ${wide ? "field--wide" : ""} ${error ? "field--invalid" : ""}`}>
      {!labelledBy && <span>{label}</span>}
      {f.kind === "select" ? (
        <select id={id} value={text} required={f.required} onChange={(e) => onChange(e.target.value)} {...aria}>
          <option value="" disabled={f.required}>
            {f.placeholder || t("choose")}
          </option>
          {(f.options ?? []).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          name={f.name}
          type={f.kind}
          value={text}
          required={f.required}
          placeholder={f.placeholder}
          inputMode={f.kind === "number" ? "decimal" : undefined}
          autoComplete={AUTOCOMPLETE[f.kind] ?? "off"}
          onChange={(e) => onChange(e.target.value)}
          {...aria}
        />
      )}
      {errorLine}
    </label>
  );
}

const AUTOCOMPLETE: Partial<Record<FormField["kind"], string>> = { email: "email", tel: "tel" };
