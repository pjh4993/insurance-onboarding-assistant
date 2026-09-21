import type { Attributes, Context, Link, SpanKind } from "@opentelemetry/api";
import {
  AlwaysOnSampler,
  ParentBasedSampler,
  type Sampler,
  SamplingDecision,
  type SamplingResult,
} from "@opentelemetry/sdk-trace-base";

// Health checks and long-lived SSE relays: one span per connection says nothing and costs volume.
const QUIET = [/\/healthz\b/, /\/stream\b/];

export function isQuiet(spanName: string, attributes: Attributes): boolean {
  const target = [spanName, attributes["http.target"], attributes["url.path"], attributes["http.route"]]
    .filter((v): v is string => typeof v === "string")
    .join(" ");
  return QUIET.some((re) => re.test(target));
}

/** Drops root spans for quiet paths; everything else follows the parent (and is on at the root). */
export class QuietPathsSampler implements Sampler {
  private readonly inner = new ParentBasedSampler({ root: new AlwaysOnSampler() });

  shouldSample(
    context: Context,
    traceId: string,
    spanName: string,
    spanKind: SpanKind,
    attributes: Attributes,
    links: Link[],
  ): SamplingResult {
    if (isQuiet(spanName, attributes)) return { decision: SamplingDecision.NOT_RECORD };
    return this.inner.shouldSample(context, traceId, spanName, spanKind, attributes, links);
  }

  toString(): string {
    return "QuietPathsSampler";
  }
}
