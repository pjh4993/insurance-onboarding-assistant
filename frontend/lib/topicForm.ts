// Pure helpers for topic forms (Prompt.form): the UI state, required checks and the submit payload (unit-tested).
import type { FormField, FormFieldValue, FormSpec, TopicAnswer } from "./types";

/** What the inputs hold: strings for text-like kinds, a boolean for checkboxes, an array for multiselect. */
export type FieldState = string | boolean | string[];
export type FormState = Record<string, FieldState>;
export type FieldError = "required" | "number";

/** The inputs' starting values, from each field's pre-filled `value`. */
export function initialFormState(form: FormSpec): FormState {
  const state: FormState = {};
  for (const f of form.fields) state[f.name] = initialFieldState(f);
  return state;
}

function initialFieldState(f: FormField): FieldState {
  const v = f.value;
  switch (f.kind) {
    case "boolean":
      return v === true || v === "true";
    case "multiselect":
      return Array.isArray(v) ? v.map(String) : v === undefined || v === null || v === "" ? [] : [String(v)];
    case "date":
      // <input type="date"> takes YYYY-MM-DD only; a pre-filled timestamp keeps its date part.
      return typeof v === "string" ? v.slice(0, 10) : "";
    default:
      return v === undefined || v === null ? "" : String(v);
  }
}

function isEmpty(f: FormField, v: FieldState | undefined): boolean {
  if (f.kind === "boolean") return false; // unchecked is an answer (false)
  if (Array.isArray(v)) return v.length === 0;
  return typeof v !== "string" || v.trim() === "";
}

/** One field's error, or null when its value can be sent. */
export function validateField(f: FormField, v: FieldState | undefined): FieldError | null {
  if (isEmpty(f, v)) return f.required ? "required" : null;
  if (f.kind === "number" && !Number.isFinite(Number(String(v).trim()))) return "number";
  return null;
}

/** Errors by field name; empty when the form can be sent. */
export function validateForm(form: FormSpec, state: FormState): Record<string, FieldError> {
  const errors: Record<string, FieldError> = {};
  for (const f of form.fields) {
    const error = validateField(f, state[f.name]);
    if (error) errors[f.name] = error;
  }
  return errors;
}

/** The first field still to answer in a stepped form: the first invalid one, else the first empty one. */
export function firstOpenField(form: FormSpec, state: FormState): number {
  const invalid = form.fields.findIndex((f) => validateField(f, state[f.name]));
  if (invalid >= 0) return invalid;
  const empty = form.fields.findIndex((f) => f.kind !== "boolean" && isEmpty(f, state[f.name]));
  return empty >= 0 ? empty : form.fields.length - 1;
}

/**
 * How an answered field reads in the stepped form's list above the current question: option labels for
 * choices, "" for an empty optional field and a masked document number (only its last 4 characters show),
 * since the list stays on screen while the customer answers the rest.
 */
export function answerSummary(f: FormField, v: FieldState | undefined, yesNo: { yes: string; no: string }): string {
  if (f.kind === "boolean") return v === true ? yesNo.yes : yesNo.no;
  if (isEmpty(f, v)) return "";
  const label = (value: string) => f.options?.find((o) => o.value === value)?.label ?? value;
  if (Array.isArray(v)) return v.map(label).join(", ");
  const text = String(v).trim();
  if (f.kind === "select") return label(text);
  if (f.name.endsWith("_number") && text.length > 4) return `${"•".repeat(Math.min(text.length - 4, 8))}${text.slice(-4)}`;
  return text;
}

/**
 * The `data` for IDENTITY_INFO / NEEDS: `{topic, fields}` with typed values (numbers as numbers, booleans,
 * multiselect arrays). Empty optional fields are left out so they do not overwrite what the backend knows.
 * Call validateForm first; invalid numbers are left out here as well.
 */
export function buildTopicAnswer(form: FormSpec, state: FormState): TopicAnswer {
  const fields: Record<string, FormFieldValue> = {};
  for (const f of form.fields) {
    const v = state[f.name];
    if (f.kind === "boolean") {
      fields[f.name] = v === true;
      continue;
    }
    if (isEmpty(f, v)) continue;
    if (f.kind === "multiselect") {
      fields[f.name] = [...(v as string[])];
    } else if (f.kind === "number") {
      const n = Number(String(v).trim());
      if (Number.isFinite(n)) fields[f.name] = n;
    } else {
      fields[f.name] = String(v).trim();
    }
  }
  return { topic: form.topic, fields };
}
