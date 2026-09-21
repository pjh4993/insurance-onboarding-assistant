import { ROOT_CONTEXT, SpanKind } from "@opentelemetry/api";
import { SamplingDecision } from "@opentelemetry/sdk-trace-base";
import { describe, expect, it } from "vitest";
import { QuietPathsSampler } from "./sampler";

const sample = (name: string, attributes = {}) =>
  new QuietPathsSampler().shouldSample(ROOT_CONTEXT, "0".repeat(31) + "1", name, SpanKind.SERVER, attributes, [])
    .decision;

describe("QuietPathsSampler", () => {
  it("drops health checks and SSE relays", () => {
    expect(sample("GET /healthz")).toBe(SamplingDecision.NOT_RECORD);
    expect(sample("GET", { "http.target": "/api/agent/sessions/abc/stream" })).toBe(SamplingDecision.NOT_RECORD);
    expect(sample("GET /api/customer/session/stream")).toBe(SamplingDecision.NOT_RECORD);
  });

  it("keeps everything else", () => {
    expect(sample("POST /api/agent/sessions")).toBe(SamplingDecision.RECORD_AND_SAMPLED);
    expect(sample("GET /s/[token]")).toBe(SamplingDecision.RECORD_AND_SAMPLED);
  });
});
