"use client";

import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";
import { buildTopicAnswer, initialFormState, validateForm, type FieldError, type FormState } from "@/lib/topicForm";
import type { FormField, FormSpec } from "@/lib/types";
import { TextComposer, type Submit } from "./forms";

/**
 * A small topic form from `prompt.form` (IDENTITY_INFO or NEEDS): title, why we ask, the fields and a
 * submit button. With `allow_text` on a NEEDS prompt, a free-text composer sits under it as well. Used by
 * the customer chat and by the agent console. Remount it (key) when the prompt's form changes.
 */
export function TopicForm({
  form,
  type,
  onSubmit,
  disabled,
  textPlaceholder,
}: {
  form: FormSpec;
  type: "IDENTITY_INFO" | "NEEDS";
  onSubmit: Submit;
  disabled: boolean;
  textPlaceholder: string;
}) {
  const t = useTranslations("topicForm");
  const id = useId();
  const [state, setState] = useState<FormState>(() => initialFormState(form));
  const [errors, setErrors] = useState<Record<string, FieldError>>({});
  // IDENTITY_INFO takes form answers only (contract); free text is a NEEDS answer.
  const allowText = form.allow_text && type === "NEEDS";

  function set(name: string, value: FormState[string]) {
    setState((s) => ({ ...s, [name]: value }));
    setErrors((e) => {
      if (!(name in e)) return e;
      const next = { ...e };
      delete next[name];
      return next;
    });
  }

  async function handle(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const found = validateForm(form, state);
    setErrors(found);
    const first = form.fields.find((f) => found[f.name]);
    if (first) {
      document.getElementById(`${id}-${first.name}`)?.focus();
      return;
    }
    await onSubmit({ type, data: buildTopicAnswer(form, state) });
  }

  const titleId = `${id}-title`;
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
      {allowText && (
        <div className="topic-form__text">
          <p className="topic-form__or">{t("orText")}</p>
          <TextComposer
            disabled={disabled}
            placeholder={textPlaceholder}
            onSend={(text) => onSubmit({ type: "NEEDS", data: { text } })}
          />
        </div>
      )}
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
}: {
  id: string;
  field: FormField;
  value: FormState[string] | undefined;
  error: FieldError | undefined;
  wide: boolean;
  onChange: (v: FormState[string]) => void;
}) {
  const t = useTranslations("topicForm");
  const errId = `${id}-error`;
  const aria = { "aria-invalid": error ? true : undefined, "aria-describedby": error ? errId : undefined };
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
      <span>{label}</span>
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
