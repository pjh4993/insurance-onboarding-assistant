import { logs, SeverityNumber } from "@opentelemetry/api-logs";

type Level = "info" | "warn" | "error";

const SEVERITY: Record<Level, SeverityNumber> = {
  info: SeverityNumber.INFO,
  warn: SeverityNumber.WARN,
  error: SeverityNumber.ERROR,
};

/** Cap on one log line (message, and separately a stack's tail) and on span attribute values. */
export function logMaxChars(): number {
  const n = Number(process.env.LOG_MAX_CHARS);
  return Number.isInteger(n) && n > 0 ? n : 2000;
}

export function truncate(text: string, limit: number, keep: "head" | "tail" = "head"): string {
  if (text.length <= limit) return text;
  const marker = `…[+${text.length - limit} chars]`;
  return keep === "head" ? text.slice(0, limit) + marker : marker + text.slice(-limit);
}

/** Render a log line: the message capped from the head, an error's stack capped from the tail. */
export function formatLine(message: string, err?: unknown, limit = logMaxChars()): string {
  const head = truncate(message, limit);
  if (err === undefined) return head;
  const detail = err instanceof Error ? (err.stack ?? `${err.name}: ${err.message}`) : String(err);
  return `${head}\n${truncate(detail, limit, "tail")}`;
}

/** Log to stdout (CloudWatch) and, when OTel is registered, over OTLP. A no-op provider drops the second. */
export function log(level: Level, message: string, err?: unknown): void {
  const line = formatLine(message, err);
  (level === "info" ? console.log : console[level])(line);
  logs.getLogger("onboarding-frontend").emit({
    severityNumber: SEVERITY[level],
    severityText: level.toUpperCase(),
    body: line,
  });
}
