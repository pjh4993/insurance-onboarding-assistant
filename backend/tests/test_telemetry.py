import logging

from app.telemetry import CapLength, DropHealthChecks, truncate


def _record(msg: str, *args, exc_info=None) -> logging.LogRecord:
    return logging.LogRecord("app", logging.ERROR, __file__, 1, msg, args, exc_info)


def test_truncate_marks_what_was_cut():
    assert truncate("abcdef", 10) == "abcdef"
    assert truncate("abcdef", 4) == "abcd…[+2 chars]"
    assert truncate("abcdef", 4, keep="tail") == "…[+2 chars]cdef"


def test_cap_renders_args_and_bounds_the_message():
    record = _record("payload=%s", "x" * 5000)
    CapLength(100).filter(record)
    assert record.args is None
    assert record.getMessage().startswith("payload=xxx")
    assert record.getMessage().endswith("…[+4908 chars]")
    assert record.trace_id == "-"


def test_cap_keeps_the_traceback_tail_and_runs_once():
    try:
        raise ValueError("the real error")
    except ValueError:
        import sys

        record = _record("failed", exc_info=sys.exc_info())
    cap = CapLength(40)
    cap.filter(record)
    once = record.getMessage()
    assert once.startswith("failed\n…[+") and once.endswith("ValueError: the real error\n")
    assert record.exc_info is None
    cap.filter(record)  # second handler sharing the record
    assert record.getMessage() == once


def test_health_checks_are_dropped_from_access_logs():
    drop = DropHealthChecks()
    assert not drop.filter(_record('10.0.0.1:1 - "GET /healthz HTTP/1.1" 200'))
    assert drop.filter(_record('10.0.0.1:1 - "POST /api/sessions HTTP/1.1" 201'))
