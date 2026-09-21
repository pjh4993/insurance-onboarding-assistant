import json
import logging
import sys

from app.telemetry import AccessFields, CapLength, DropHealthChecks, JsonFormatter, record_fields, truncate


def _record(msg: str, *args, exc_info=None, name: str = "app", **extra) -> logging.LogRecord:
    record = logging.LogRecord(name, logging.WARNING, __file__, 1, msg, args or None, exc_info)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def _emit(record: logging.LogRecord, max_chars: int = 100) -> dict:
    CapLength(max_chars).filter(record)
    return json.loads(JsonFormatter().format(record))


def test_truncate_marks_what_was_cut():
    assert truncate("abcdef", 10) == "abcdef"
    assert truncate("abcdef", 4) == "abcd…[+2 chars]"
    assert truncate("abcdef", 4, keep="tail") == "…[+2 chars]cdef"


def test_one_json_object_per_line_with_extra_fields():
    line = JsonFormatter().format(_record("graph run failed", session_id="s-1", **{"error.type": "Timeout"}))
    assert "\n" not in line
    entry = json.loads(line)
    assert entry["level"] == "WARNING" and entry["logger"] == "app" and entry["msg"] == "graph run failed"
    assert entry["session_id"] == "s-1" and entry["error.type"] == "Timeout"
    assert entry["ts"].endswith("+00:00")
    assert "trace_id" not in entry  # outside a span


def test_message_and_fields_are_capped():
    entry = _emit(_record("payload=%s", "x" * 5000, answer="y" * 500))
    assert entry["msg"] == "payload=" + "x" * 92 + "…[+4908 chars]"
    assert entry["answer"] == "y" * 100 + "…[+400 chars]"


def test_traceback_moves_to_exception_fields_keeping_its_tail():
    try:
        raise ValueError("the real error")
    except ValueError:
        record = _record("failed", exc_info=sys.exc_info())
    entry = _emit(record, max_chars=40)
    assert entry["msg"] == "failed"
    assert entry["exception.type"] == "ValueError"
    assert entry["exception.message"] == "the real error"
    assert entry["exception.stacktrace"].startswith("…[+")
    assert entry["exception.stacktrace"].endswith("ValueError: the real error\n")
    assert record.exc_info is None


def test_capping_runs_once_across_handlers():
    record = _record("m" * 60)
    CapLength(50).filter(record)
    first = record.getMessage()
    CapLength(50).filter(record)  # the OTLP handler's filter sees the same record
    assert record.getMessage() == first == "m" * 50 + "…[+10 chars]"
    assert "capped" not in json.dumps(record_fields(record))


def test_access_line_is_split_into_fields():
    args = ("10.0.0.1:1", "POST", "/api/sessions", "1.1", 201)
    record = _record('%s - "%s %s HTTP/%s" %d', *args, name="uvicorn.access")
    AccessFields().filter(record)
    entry = _emit(record, max_chars=500)
    assert entry["msg"] == '10.0.0.1:1 - "POST /api/sessions HTTP/1.1" 201'
    assert entry["http.request.method"] == "POST"
    assert entry["url.path"] == "/api/sessions"
    assert entry["http.response.status_code"] == 201


def test_health_checks_are_dropped_from_access_logs():
    drop = DropHealthChecks()
    assert not drop.filter(_record('%s - "%s %s HTTP/%s" %d', "a", "GET", "/healthz", "1.1", 200))
    assert drop.filter(_record('%s - "%s %s HTTP/%s" %d', "a", "POST", "/api/sessions", "1.1", 201))
