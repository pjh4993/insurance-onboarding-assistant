import type { Instrumentation } from "next";

// Registers OpenTelemetry on the Node runtime when an OTLP endpoint is configured; the exporters read
// OTEL_EXPORTER_OTLP_ENDPOINT / OTEL_EXPORTER_OTLP_HEADERS / OTEL_SERVICE_NAME from the environment.
export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME !== "nodejs" || !process.env.OTEL_EXPORTER_OTLP_ENDPOINT) return;

  const [{ registerOTel }, { OTLPLogExporter }, { BatchLogRecordProcessor }, { QuietPathsSampler }, { logMaxChars }] =
    await Promise.all([
      import("@vercel/otel"),
      import("@opentelemetry/exporter-logs-otlp-http"),
      import("@opentelemetry/sdk-logs"),
      import("./lib/server/sampler"),
      import("./lib/server/log"),
    ]);

  registerOTel({
    serviceName: "onboarding-frontend",
    traceSampler: new QuietPathsSampler(),
    spanLimits: { attributeValueLengthLimit: logMaxChars() },
    // Send traceparent to the backend so one trace spans the relay and the API call.
    instrumentationConfig: {
      fetch: { propagateContextUrls: process.env.BACKEND_URL ? [process.env.BACKEND_URL] : [] },
    },
    logRecordProcessors: [new BatchLogRecordProcessor({ exporter: new OTLPLogExporter() })],
  });
}

export const onRequestError: Instrumentation.onRequestError = async (err, request) => {
  const { log } = await import("./lib/server/log");
  log("error", "request failed", { "http.request.method": request.method, "url.path": request.path }, err);
};
