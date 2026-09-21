"""Bedrock Converse (and ConverseStream) response builder.

The response must parse in botocore's restJson parser, so field names and nesting follow the
Converse API exactly. Errors carry `x-amzn-ErrorType` so botocore raises the named exception
(ThrottlingException, InternalServerException, ...).
"""

from __future__ import annotations

import binascii
import copy
import json
import struct
import time
import uuid
from typing import Any

from fastapi.responses import JSONResponse

from . import fixtures
from .seed import find_in_text

TOOL_NAMES = {
    "needsextraction": "NeedsExtraction",
    "recommendationrationale": "RecommendationRationale",
    "partiesextraction": "PartiesExtraction",
    "answersextraction": "AnswersExtraction",
    "applicationsummary": "ApplicationSummary",
    "intakereply": "IntakeReply",
}


def _strings(node: Any) -> list[str]:
    """Every string value nested in `node` (texts, tool results, tool inputs)."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _strings(v)]
    return []


def last_user_text(body: dict[str, Any]) -> str:
    """The latest user message alone: the system prompt lists every product, so it must not be searched."""
    for message in reversed(body.get("messages") or []):
        if message.get("role") == "user":
            return "\n".join(_strings(message.get("content", [])))
    return ""


def request_text(body: dict[str, Any]) -> str:
    return "\n".join(_strings(body.get("system", [])) + _strings(body.get("messages", [])))


def pick_tool(body: dict[str, Any]) -> str | None:
    config = body.get("toolConfig") or {}
    names = [t["toolSpec"]["name"] for t in config.get("tools", []) if "toolSpec" in t]
    if not names:
        return None
    forced = (config.get("toolChoice") or {}).get("tool", {}).get("name")
    return forced if forced in names else names[0]


def tool_input(tool_name: str, text: str) -> dict[str, Any]:
    customer = find_in_text(text)
    key = customer["key"] if customer else None
    canonical = TOOL_NAMES.get(tool_name.replace("_", "").casefold())
    match canonical:
        case "NeedsExtraction":
            return copy.deepcopy(fixtures.NEEDS[key]) if key else fixtures.generic_needs(text)
        case "RecommendationRationale":
            items = [
                {"recommendation_id": rec["recommendation_id"], "rationale": fixtures.rationale_for(rec, key)}
                for rec in fixtures.find_recommendations(text)
            ]
            return {"items": items}
        case "PartiesExtraction":
            return copy.deepcopy(fixtures.PARTIES[key]) if key else {"all_self": True, "parties": []}
        case "AnswersExtraction":
            return copy.deepcopy(fixtures.ANSWERS[key]) if key else {"answers": {}, "missing_fields": []}
        case "ApplicationSummary":
            return {"summary": fixtures.SUMMARY[key] if key else fixtures.GENERIC_SUMMARY}
        case _:
            return {}


def text_reply(text: str) -> str:
    customer = find_in_text(text)
    market = customer["market"] if customer else "US"
    return fixtures.TEXT_REPLY[market]


def _tokens(s: str) -> int:
    return max(1, len(s) // 4)


def converse_result(body: dict[str, Any], started: float) -> dict[str, Any]:
    text = request_text(body)
    tool = pick_tool(body)
    if tool:
        canonical = TOOL_NAMES.get(tool.replace("_", "").casefold())
        payload = (
            fixtures.intake_reply(last_user_text(body))
            if canonical == "IntakeReply"
            else tool_input(tool, text)
        )
        content = [
            {"toolUse": {"toolUseId": f"tooluse_{uuid.uuid4().hex[:22]}", "name": tool, "input": payload}}
        ]
        stop_reason = "tool_use"
        out_tokens = _tokens(json.dumps(payload, ensure_ascii=False))
    else:
        reply = text_reply(text)
        content = [{"text": reply}]
        stop_reason = "end_turn"
        out_tokens = _tokens(reply)
    in_tokens = _tokens(text)
    return {
        "output": {"message": {"role": "assistant", "content": content}},
        "stopReason": stop_reason,
        "usage": {
            "inputTokens": in_tokens,
            "outputTokens": out_tokens,
            "totalTokens": in_tokens + out_tokens,
        },
        "metrics": {"latencyMs": max(1, int((time.monotonic() - started) * 1000))},
    }


# --- errors ---------------------------------------------------------------------------------------------

_ERRORS = {
    "429": (429, "ThrottlingException", "Too many requests, please wait before trying again."),
    "500": (500, "InternalServerException", "The server encountered an internal error."),
    "timeout": (504, "ModelTimeoutException", "The request took too long to process."),
}


def error_response(kind: str) -> JSONResponse:
    status, code, message = _ERRORS[kind]
    return JSONResponse(
        {"message": message},
        status_code=status,
        headers={"x-amzn-ErrorType": f"{code}:http://internal.amazon.com/coral/com.amazon.bedrock/"},
    )


def validation_error(message: str) -> JSONResponse:
    return JSONResponse(
        {"message": message},
        status_code=400,
        headers={
            "x-amzn-ErrorType": "ValidationException:http://internal.amazon.com/coral/com.amazon.bedrock/"
        },
    )


# --- ConverseStream (application/vnd.amazon.eventstream) ------------------------------------------------


def _header(name: str, value: str) -> bytes:
    n, v = name.encode(), value.encode()
    return struct.pack("B", len(n)) + n + b"\x07" + struct.pack(">H", len(v)) + v


def encode_event(event_type: str, payload: dict[str, Any]) -> bytes:
    headers = (
        _header(":event-type", event_type)
        + _header(":content-type", "application/json")
        + _header(":message-type", "event")
    )
    body = json.dumps(payload, ensure_ascii=False).encode()
    total = 12 + len(headers) + len(body) + 4
    prelude = struct.pack(">II", total, len(headers))
    prelude += struct.pack(">I", binascii.crc32(prelude) & 0xFFFFFFFF)
    message = prelude + headers + body
    return message + struct.pack(">I", binascii.crc32(message) & 0xFFFFFFFF)


def stream_events(result: dict[str, Any]) -> bytes:
    """Replay a complete Converse result as ConverseStream events."""
    block = result["output"]["message"]["content"][0]
    events = [encode_event("messageStart", {"role": "assistant"})]
    if "toolUse" in block:
        tu = block["toolUse"]
        events.append(
            encode_event(
                "contentBlockStart",
                {
                    "contentBlockIndex": 0,
                    "start": {"toolUse": {"toolUseId": tu["toolUseId"], "name": tu["name"]}},
                },
            )
        )
        delta = {"toolUse": {"input": json.dumps(tu["input"], ensure_ascii=False)}}
    else:
        delta = {"text": block["text"]}
    events.append(encode_event("contentBlockDelta", {"contentBlockIndex": 0, "delta": delta}))
    events.append(encode_event("contentBlockStop", {"contentBlockIndex": 0}))
    events.append(encode_event("messageStop", {"stopReason": result["stopReason"]}))
    events.append(encode_event("metadata", {"usage": result["usage"], "metrics": result["metrics"]}))
    return b"".join(events)
