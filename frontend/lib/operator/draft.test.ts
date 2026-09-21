import { describe, expect, it } from "vitest";
import { addLanguage, asShapeOf, getIn, parseBundle, placeholders, serializeBundle, setIn, textOf } from "./draft";

const files = {
  "config.json": JSON.stringify({
    version: "1.0.0",
    languages: { ko: { name: "Korean" }, en: { name: "English" } },
    default_language: "en",
    system_prompt: ["You are an assistant.", "{instructions}"],
    labels: { age_range: { ko: "나이", en: "your age" } },
    billing_periods: { MONTHLY: { ko: "월", en: "month" } },
    flows: { profiling: "flows/profiling.json" },
  }),
  "flows/profiling.json": JSON.stringify({
    llm: { assess_needs: { model: "default", instructions: "Extract {values}" } },
    copy: { ask_more: { ko: "{fields} 알려 주세요", en: "Tell me {fields}" } },
  }),
};

describe("draft", () => {
  it("round-trips a bundle", () => {
    const doc = parseBundle(files);
    const out = serializeBundle(doc);
    expect(JSON.parse(out["config.json"])).toEqual(JSON.parse(files["config.json"]));
    expect(JSON.parse(out["flows/profiling.json"])).toEqual(JSON.parse(files["flows/profiling.json"]));
  });

  it("edits one field, keeping the shape a text had", () => {
    const doc = parseBundle(files);
    const prompt = getIn(doc, ["config", "system_prompt"]);
    expect(textOf(prompt)).toBe("You are an assistant.\n{instructions}");
    const edited = setIn(doc, ["config", "system_prompt"], asShapeOf(prompt, "You help.\n\n{instructions}"));
    expect(edited.config.system_prompt).toEqual(["You help.", "", "{instructions}"]);
    const copy = setIn(edited, ["profiling", "copy", "ask_more", "en"], "Please tell me {fields}.");
    expect(getIn(copy, ["profiling", "copy", "ask_more", "en"])).toBe("Please tell me {fields}.");
    expect(getIn(doc, ["profiling", "copy", "ask_more", "en"])).toBe("Tell me {fields}"); // the original stays
  });

  it("finds placeholders, not literal braces", () => {
    expect(placeholders("Tell me {fields} and {fields}, {{literal}}")).toEqual(["fields"]);
  });

  it("adds a language with every text starting from the default language", () => {
    const doc = addLanguage(parseBundle(files), "ja", "Japanese");
    expect(doc.config.languages).toMatchObject({ ja: { name: "Japanese" } });
    expect(getIn(doc, ["config", "labels", "age_range", "ja"])).toBe("your age");
    expect(getIn(doc, ["profiling", "copy", "ask_more", "ja"])).toBe("Tell me {fields}");
  });
});
