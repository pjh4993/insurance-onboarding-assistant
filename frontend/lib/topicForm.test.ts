import { describe, expect, it } from "vitest";
import { answerSummary, buildTopicAnswer, firstOpenField, initialFormState, validateField, validateForm } from "./topicForm";
import type { FormSpec } from "./types";

const form: FormSpec = {
  topic: "trip",
  title: "Your trip",
  reason: "To price the cover",
  allow_text: true,
  fields: [
    { name: "destination", label: "Destination", kind: "text", required: true },
    { name: "email", label: "Email", kind: "email", required: false },
    { name: "start_date", label: "Start", kind: "date", required: true, value: "2026-10-01T00:00:00Z" },
    { name: "travellers", label: "Travellers", kind: "number", required: false, value: 2 },
    {
      name: "purpose",
      label: "Purpose",
      kind: "select",
      required: false,
      options: [
        { value: "LEISURE", label: "Leisure" },
        { value: "BUSINESS", label: "Business" },
      ],
    },
    {
      name: "activities",
      label: "Activities",
      kind: "multiselect",
      required: false,
      options: [
        { value: "SKI", label: "Skiing" },
        { value: "DIVE", label: "Diving" },
      ],
      value: ["SKI"],
    },
    { name: "pre_existing", label: "Any conditions?", kind: "boolean", required: false },
  ],
};

describe("initialFormState", () => {
  it("pre-fills values in the shape each input takes", () => {
    expect(initialFormState(form)).toEqual({
      destination: "",
      email: "",
      start_date: "2026-10-01",
      travellers: "2",
      purpose: "",
      activities: ["SKI"],
      pre_existing: false,
    });
  });

  it("reads a pre-filled true boolean and a single multiselect value", () => {
    const f: FormSpec = {
      ...form,
      fields: [
        { name: "consent", label: "c", kind: "boolean", required: false, value: true },
        { name: "m", label: "m", kind: "multiselect", required: false, value: "A" },
      ],
    };
    expect(initialFormState(f)).toEqual({ consent: true, m: ["A"] });
  });
});

describe("validateForm", () => {
  it("flags empty required fields, including whitespace", () => {
    const state = { ...initialFormState(form), destination: "   ", start_date: "" };
    expect(validateForm(form, state)).toEqual({ destination: "required", start_date: "required" });
  });

  it("flags an empty required multiselect but never a boolean", () => {
    const f: FormSpec = {
      ...form,
      fields: [
        { name: "m", label: "m", kind: "multiselect", required: true, options: [] },
        { name: "b", label: "b", kind: "boolean", required: true },
      ],
    };
    expect(validateForm(f, { m: [], b: false })).toEqual({ m: "required" });
  });

  it("flags a number that does not parse", () => {
    expect(validateForm(form, { ...initialFormState(form), destination: "Tokyo", travellers: "two" })).toEqual({
      travellers: "number",
    });
  });

  it("passes a complete form", () => {
    expect(validateForm(form, { ...initialFormState(form), destination: "Tokyo" })).toEqual({});
  });
});

describe("buildTopicAnswer", () => {
  it("types the values and omits empty optional fields", () => {
    const state = { ...initialFormState(form), destination: " Tokyo ", travellers: "3", pre_existing: true };
    expect(buildTopicAnswer(form, state)).toEqual({
      topic: "trip",
      fields: {
        destination: "Tokyo",
        start_date: "2026-10-01",
        travellers: 3,
        activities: ["SKI"],
        pre_existing: true,
      },
    });
  });

  it("sends an unchecked boolean as false and drops an emptied multiselect", () => {
    const state = { ...initialFormState(form), destination: "Seoul", activities: [], travellers: "" };
    const { fields } = buildTopicAnswer(form, state);
    expect(fields.pre_existing).toBe(false);
    expect(fields).not.toHaveProperty("activities");
    expect(fields).not.toHaveProperty("travellers");
    expect(fields).not.toHaveProperty("email");
  });

  it("keeps a select choice and decimal numbers", () => {
    const state = { ...initialFormState(form), destination: "Paris", purpose: "BUSINESS", travellers: "1.5" };
    const { fields } = buildTopicAnswer(form, state);
    expect(fields.purpose).toBe("BUSINESS");
    expect(fields.travellers).toBe(1.5);
  });
});

describe("stepped form helpers", () => {
  const yesNo = { yes: "Yes", no: "No" };
  const field = (name: string) => form.fields.find((f) => f.name === name)!;

  it("checks one field at a time", () => {
    expect(validateField(field("destination"), " ")).toBe("required");
    expect(validateField(field("email"), "")).toBeNull();
    expect(validateField(field("travellers"), "two")).toBe("number");
    expect(validateField(field("travellers"), "2")).toBeNull();
  });

  it("opens at the first field that still needs an answer", () => {
    const state = initialFormState(form);
    expect(firstOpenField(form, state)).toBe(0);
    state.destination = "Tokyo";
    expect(firstOpenField(form, state)).toBe(1); // optional email is empty: ask it, skippable
    state.email = "a@b.co";
    state.purpose = "LEISURE";
    expect(firstOpenField(form, state)).toBe(form.fields.length - 1); // only the checkbox left
  });

  it("summarises answers with option labels and masks document numbers", () => {
    expect(answerSummary(field("purpose"), "BUSINESS", yesNo)).toBe("Business");
    expect(answerSummary(field("activities"), ["SKI", "DIVE"], yesNo)).toBe("Skiing, Diving");
    expect(answerSummary(field("pre_existing"), true, yesNo)).toBe("Yes");
    expect(answerSummary(field("email"), "", yesNo)).toBe("");
    const doc = { name: "id_document_number", label: "Number", kind: "text" as const, required: true };
    expect(answerSummary(doc, "900101-1234567", yesNo)).toBe("••••••••4567");
  });
});
