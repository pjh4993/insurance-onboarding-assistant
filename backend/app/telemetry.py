"""Structured logging and OpenTelemetry setup.

Logs go to stdout as one JSON object per line (CloudWatch), and also over OTLP when
OTEL_EXPORTER_OTLP_ENDPOINT is set, with the same fields as log attributes. Context goes in fields,
not in the message: `log.warning("graph run failed", extra={"session_id": sid})`. Every string is
capped at `log_max_chars`.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
import weakref
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace

from app.config import Settings

# Paths excluded from traces: health checks and long-lived SSE streams (one span per connection, not per event).
EXCLUDED_URLS = "/healthz,/stream"
NOISY_LOGGERS = ("httpx", "httpcore", "botocore", "urllib3", "psycopg", "langchain", "langgraph")
# uvicorn.error propagates to "uvicorn"; uvicorn.access does not propagate at all.
UVICORN_LOGGERS = ("uvicorn", "uvicorn.access")

# Attributes every LogRecord has; anything else on a record came from `extra=` or a filter here.
_RESERVED = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
    "color_message",  # uvicorn's ANSI-colored copy of msg
}

_otel_ready = False
# Records already capped: the stdout and OTLP handlers each run a CapLength on the same record.
_capped: weakref.WeakSet[logging.LogRecord] = weakref.WeakSet()


def truncate(text: str, limit: int, keep: str = "head") -> str:
    if len(text) <= limit:
        return text
    cut = len(text) - limit
    marker = f"…[+{cut} chars]"
    return text[:limit] + marker if keep == "head" else marker + text[-limit:]


def record_fields(record: logging.LogRecord) -> dict[str, Any]:
    """The structured fields of a record: its `extra=` keys and those added by the filters below."""
    return {k: v for k, v in vars(record).items() if k not in _RESERVED and not k.startswith("_")}


class CapLength(logging.Filter):
    """Render the message once and cap it; cap every string field; move a traceback into exception.* fields."""

    def __init__(self, max_chars: int) -> None:
        super().__init__()
        self.max_chars = max_chars

    def filter(self, record: logging.LogRecord) -> bool:
        if record in _capped:
            return True
        _capped.add(record)
        record.msg, record.args = truncate(record.getMessage(), self.max_chars), None
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            stack = "".join(traceback.format_exception(*record.exc_info))
            setattr(record, "exception.type", type(exc).__name__)
            setattr(record, "exception.message", truncate(str(exc), self.max_chars))
            setattr(record, "exception.stacktrace", truncate(stack, self.max_chars, keep="tail"))
            record.exc_info = None
            record.exc_text = None
        for key, value in record_fields(record).items():
            if isinstance(value, str) and key != "exception.stacktrace":
                setattr(record, key, truncate(value, self.max_chars))
        return True


class AccessFields(logging.Filter):
    """Split uvicorn's access line into fields (it logs `client - "METHOD path HTTP/x" status` with args)."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) == 5:
            client, method, path, http_version, status = args
            setattr(record, "client.address", str(client))
            setattr(record, "http.request.method", method)
            setattr(record, "url.path", path)
            setattr(record, "network.protocol.version", http_version)
            setattr(record, "http.response.status_code", int(status))
        return True


class DropHealthChecks(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/healthz" not in record.getMessage()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        span = trace.get_current_span().get_span_context()
        if span.is_valid:
            entry["trace_id"] = f"{span.trace_id:032x}"
            entry["span_id"] = f"{span.span_id:016x}"
        entry.update(record_fields(record))
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CapLength(settings.log_max_chars))
    handler.set_name("app-stdout")

    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if h.get_name() != "app-stdout"]
    root.addHandler(handler)
    root.setLevel(settings.log_level)
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    # uvicorn configures its own plain-text handlers and does not propagate; give them the JSON one.
    for name in UVICORN_LOGGERS:
        logging.getLogger(name).handlers = [handler]
    access = logging.getLogger("uvicorn.access")
    access.filters = [DropHealthChecks(), AccessFields()]


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
        # Record fields become log attributes; the handler adds trace and span ids itself.
        otlp = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        otlp.addFilter(CapLength(settings.log_max_chars))
        for name in ("", *UVICORN_LOGGERS):
            logging.getLogger(name).addHandler(otlp)

        HTTPXClientInstrumentor().instrument()
        BotocoreInstrumentor().instrument()
        _otel_ready = True

    # The ASGI receive/send sub-spans add volume without saying anything the request span does not.
    FastAPIInstrumentor.instrument_app(app, excluded_urls=EXCLUDED_URLS, exclude_spans=["receive", "send"])
