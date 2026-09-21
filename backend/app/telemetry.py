"""Logging and OpenTelemetry setup. Logs always go to stdout (CloudWatch); traces and logs also go over
OTLP when OTEL_EXPORTER_OTLP_ENDPOINT is set. Every record is capped at `log_max_chars`."""

from __future__ import annotations

import logging
import os
import sys
import traceback

from fastapi import FastAPI
from opentelemetry import trace

from app.config import Settings

# Paths excluded from traces: health checks and long-lived SSE streams (one span per connection, not per event).
EXCLUDED_URLS = "/healthz,/stream"
NOISY_LOGGERS = ("httpx", "httpcore", "botocore", "urllib3", "psycopg", "langchain", "langgraph")

_otel_ready = False


def truncate(text: str, limit: int, keep: str = "head") -> str:
    if len(text) <= limit:
        return text
    cut = len(text) - limit
    marker = f"…[+{cut} chars]"
    return text[:limit] + marker if keep == "head" else marker + text[-limit:]


class CapLength(logging.Filter):
    """Render the message once, cap it, and fold any traceback in (its tail, where the error is)."""

    def __init__(self, max_chars: int) -> None:
        super().__init__()
        self.max_chars = max_chars

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "capped", False):  # the stdout and OTLP handlers share one record
            return True
        record.capped = True
        message = truncate(record.getMessage(), self.max_chars)
        if record.exc_info and record.exc_info[1] is not None:
            tb = "".join(traceback.format_exception(*record.exc_info))
            message = f"{message}\n{truncate(tb, self.max_chars, keep='tail')}"
            record.exc_info = None
            record.exc_text = None
        record.msg, record.args = message, None
        span = trace.get_current_span().get_span_context()
        record.trace_id = f"{span.trace_id:032x}" if span.is_valid else "-"
        return True


class DropHealthChecks(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/healthz" not in record.getMessage()


def setup_logging(settings: Settings) -> None:
    cap = CapLength(settings.log_max_chars)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s trace=%(trace_id)s %(message)s"))
    handler.addFilter(cap)
    handler.set_name("app-stdout")
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if h.get_name() != "app-stdout"]
    root.addHandler(handler)
    root.setLevel(settings.log_level)
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").addFilter(DropHealthChecks())


def setup_otel(app: FastAPI, settings: Settings) -> None:
    """Export traces and logs over OTLP; the exporters read OTEL_EXPORTER_OTLP_* from the environment."""
    global _otel_ready
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    if not _otel_ready:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import SpanLimits, TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create()  # OTEL_SERVICE_NAME and OTEL_RESOURCE_ATTRIBUTES
        tracer_provider = TracerProvider(
            resource=resource, span_limits=SpanLimits(max_attribute_length=settings.log_max_chars)
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(tracer_provider)

        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
        set_logger_provider(logger_provider)
        otlp = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        otlp.addFilter(CapLength(settings.log_max_chars))
        logging.getLogger().addHandler(otlp)

        HTTPXClientInstrumentor().instrument()
        BotocoreInstrumentor().instrument()
        _otel_ready = True

    # The ASGI receive/send sub-spans add volume without saying anything the request span does not.
    FastAPIInstrumentor.instrument_app(app, excluded_urls=EXCLUDED_URLS, exclude_spans=["receive", "send"])
