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

/** Errors by field name; empty when the form can be sent. */
export function validateForm(form: FormSpec, state: FormState): Record<string, FieldError> {
  const errors: Record<string, FieldError> = {};
  for (const f of form.fields) {
    const v = state[f.name];
    if (isEmpty(f, v)) {
      if (f.required) errors[f.name] = "required";
    } else if (f.kind === "number" && !Number.isFinite(Number(String(v).trim()))) {
      errors[f.name] = "number";
    }
  }
  return errors;
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
