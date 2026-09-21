import { trace } from "@opentelemetry/api";
import { logs, SeverityNumber } from "@opentelemetry/api-logs";

type Level = "info" | "warn" | "error";
export type LogFields = Record<string, string | number | boolean | undefined>;

const SEVERITY: Record<Level, SeverityNumber> = {
  info: SeverityNumber.INFO,
  warn: SeverityNumber.WARN,
  error: SeverityNumber.ERROR,
};

/** Cap on the message, on each field, and (from its tail) on a stack; also used for span attribute values. */
export function logMaxChars(): number {
  const n = Number(process.env.LOG_MAX_CHARS);
  return Number.isInteger(n) && n > 0 ? n : 2000;
}

export function truncate(text: string, limit: number, keep: "head" | "tail" = "head"): string {
  if (text.length <= limit) return text;
  const marker = `…[+${text.length - limit} chars]`;
  return keep === "head" ? text.slice(0, limit) + marker : marker + text.slice(-limit);
}

/** The structured fields of one entry: caller fields plus exception.* for an error, every string capped. */
export function entryFields(fields: LogFields = {}, err?: unknown, limit = logMaxChars()): Record<string, string | number | boolean> {
  const out: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined) out[key] = typeof value === "string" ? truncate(value, limit) : value;
  }
  if (err !== undefined) {
    const e = err instanceof Error ? err : new Error(String(err));
    out["exception.type"] = e.name;
    out["exception.message"] = truncate(e.message, limit);
    out["exception.stacktrace"] = truncate(e.stack ?? `${e.name}: ${e.message}`, limit, "tail");
  }
  return out;
}

/** One JSON object per line on stdout (CloudWatch), with the trace context of the active span. */
export function formatLine(level: Level, message: string, attrs: Record<string, string | number | boolean>): string {
  const span = trace.getActiveSpan()?.spanContext();
  return JSON.stringify({
    ts: new Date().toISOString(),
    level: level.toUpperCase(),
    logger: "onboarding-frontend",
    msg: truncate(message, logMaxChars()),
    ...(span ? { trace_id: span.traceId, span_id: span.spanId } : {}),
    ...attrs,
  });
}

/**
 * Log to stdout and, when OTel is registered, over OTLP with the same fields as attributes (a no-op provider
 * drops the second). Keep the message fixed and put context in fields: log("error", "relay failed", { … }).
 */
export function log(level: Level, message: string, fields?: LogFields, err?: unknown): void {
  const attrs = entryFields(fields, err);
  (level === "info" ? console.log : console[level])(formatLine(level, message, attrs));
  logs.getLogger("onboarding-frontend").emit({
    severityNumber: SEVERITY[level],
    severityText: level.toUpperCase(),
    body: truncate(message, logMaxChars()),
    attributes: attrs,
  });
}
