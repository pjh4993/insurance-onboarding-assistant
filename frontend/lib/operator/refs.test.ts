import { describe, expect, it } from "vitest";
import { changedRefs, nodesFor, refsInFile, refsOf, type Outline } from "./refs";

const files = {
  "config.json": JSON.stringify({
    version: "1.0.0",
    languages: { ko: { name: "Korean" }, en: { name: "English" } },
    default_language: "en",
    models: { default: { provider: "bedrock", model_id: "sonnet" }, fast: { provider: "bedrock", model_id: "haiku" } },
    system_prompt: "You are ... {instructions}",
    labels: { age_range: { ko: "나이", en: "your age" } },
    billing_periods: { MONTHLY: { ko: "월", en: "month" } },
    flows: { profiling: "flows/profiling.json", conversation: "flows/conversation.json" },
  }),
  "flows/profiling.json": JSON.stringify({
    llm: { assess_needs: { model: "fast", instructions: "Extract {values}" } },
    copy: { ask_more: { ko: "더", en: "more" } },
  }),
  "flows/conversation.json": JSON.stringify({ copy: { greeting: { ko: "안녕", en: "Hi" } } }),
};

const outline: Outline = {
  entry: "greet",
  nodes: [
    { id: "greet", domain: "conversation", kind: "code", reads: ["copy:conversation.greeting"] },
    {
      id: "assess_needs",
      domain: "profiling",
      kind: "llm",
      reads: ["copy:profiling.ask_more", "labels", "llm:assess_needs.instructions", "system_prompt"],
    },
    { id: "explain_recommendation", domain: "recommendation", kind: "llm", reads: ["billing_periods", "system_prompt"] },
  ],
  edges: [],
};
const nodeModels = { assess_needs: "fast", explain_recommendation: "default" };

describe("refsOf", () => {
  it("names every entry of a bundle", () => {
    expect([...refsOf(files).keys()].sort()).toEqual(
      [
        "billing_periods:MONTHLY",
        "copy:conversation.greeting",
        "copy:profiling.ask_more",
        "default_language",
        "labels:age_range",
        "languages",
        "llm:assess_needs.instructions",
        "llm:assess_needs.model",
        "models:default",
        "models:fast",
        "system_prompt",
      ].sort(),
    );
    expect(refsInFile(files, "flows/profiling.json")).toEqual([
      "copy:profiling.ask_more",
      "llm:assess_needs.model",
      "llm:assess_needs.instructions",
    ]);
    expect(refsInFile(files, "config.json")).toContain("models:fast");
    expect(refsOf({ "config.json": "{broken" }).size).toBe(0);
  });
});

describe("nodesFor", () => {
  it("maps each kind of entry onto the nodes that read it", () => {
    expect(nodesFor("copy:conversation.greeting", outline)).toEqual(["greet"]);
    expect(nodesFor("llm:assess_needs.instructions", outline)).toEqual(["assess_needs"]);
    expect(nodesFor("llm:assess_needs.model", outline)).toEqual(["assess_needs"]);
    expect(nodesFor("models:fast", outline, nodeModels)).toEqual(["assess_needs"]);
    expect(nodesFor("models:default", outline, nodeModels)).toEqual(["explain_recommendation"]);
    expect(nodesFor("system_prompt", outline)).toEqual(["assess_needs", "explain_recommendation"]);
    expect(nodesFor("labels:age_range", outline)).toEqual(["assess_needs"]);
    expect(nodesFor("billing_periods:MONTHLY", outline)).toEqual(["explain_recommendation"]);
    expect(nodesFor("languages", outline)).toEqual(["greet", "assess_needs", "explain_recommendation"]);
  });
});

describe("changedRefs", () => {
  it("finds the entries two bundles differ in", () => {
    const edited = {
      ...files,
      "flows/profiling.json": JSON.stringify({
        llm: { assess_needs: { model: "default", instructions: "Extract {values}" } },
        copy: { ask_more: { ko: "더", en: "tell me more" } },
      }),
    };
    expect(changedRefs(files, edited)).toEqual(["copy:profiling.ask_more", "llm:assess_needs.model"]);
    expect(changedRefs(files, files)).toEqual([]);
  });
});
