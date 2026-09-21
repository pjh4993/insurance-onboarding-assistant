"""Golden transcripts: each flow's node path, messages, session state and entities, pinned to a JSON file
under tests/golden/. They guard refactors of the agent that must not change behavior (node names stay the
same, so in-flight checkpoints keep resuming). Regenerate after an intended change with
`UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py` and review the diff."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from tests.fakes import ANSWERS, CUSTOMERS, NEEDS, identity_input

GOLDEN = Path(__file__).parent / "golden"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def needs(key: str) -> tuple:
    return ("NEEDS", {"text": CUSTOMERS[key]["needs_text"]})


def intake(text: str = "") -> tuple:
    return ("INTAKE", {"text": text})


def identity_forms(key: str, *, consent: bool) -> list[tuple]:
    """The identity details one small form at a time, as the customer UI sends them."""
    c = CUSTOMERS[key]
    return [
        ("IDENTITY_INFO", {"topic": "contact", "fields": {k: c[k] for k in ("full_name", "email", "phone")}}),
        (
            "IDENTITY_INFO",
            {"topic": "id_document", "fields": {k: c[k] for k in ("id_document_type", "id_document_number")}},
        ),
        ("IDENTITY_INFO", {"topic": "consent", "fields": {"third_party_consent": consent}}),
    ]


# A scenario is (market, steps) or (market, steps, locale). A step is an input (type, data[, actor]), a fault
# injection ("fail", "llm" | "external", target, n), a canned LLM reply for one schema ("llm_reply",
# schema_name, payload), or a language switch ("locale", "ko" | "en").
SCENARIOS: dict[str, tuple] = {
    "a_partner_match_to_submission": (
        "KR",
        [
            intake("새로 산 갤럭시 폰 보험 알아보고 있어요"),
            *identity_forms("A", consent=True),
            # forms only: merged without the LLM; the partner purchase already describes the device
            ("NEEDS", {"topic": "coverage", "fields": {"objectives": ["PROTECT_DEVICE"]}}),
            (
                "NEEDS",
                {
                    "topic": "person",
                    "fields": {"age_range": "AGE_30_39", "residence_country": "KR", "occupation": "개발자"},
                },
            ),
            ("DECISION", {"decision": "ACCEPT"}),
            ("PARTIES", {"text": "제가 피보험자이자 납입자예요."}),
            ("CONFIRM", {"confirmed": True}),
        ],
    ),
    "b_otp_travel_answers": (
        "KR",
        [
            intake(),
            ("IDENTITY_INFO", identity_input("B", consent=True)),
            ("OTP_CODE", {"code": CUSTOMERS["B"]["otp"]["valid_code"]}),
            # a form and free text together: the text goes through the LLM, the form's fields win
            ("NEEDS", {"topic": "coverage", "fields": {"objectives": ["TRAVEL_COVER"]}, "text": needs("B")[1]["text"]}),
            ("DECISION", {"decision": "ACCEPT"}),
            ("PARTIES", {"text": "저 혼자 가요."}),
            ("ANSWERS", {"text": "1985년 11월 2일생 남자입니다."}),
            ("CONFIRM", {"confirmed": False, "text": "성별은 M이에요."}),
            ("CONFIRM", {"confirmed": True}),
        ],
    ),
    "c_document_laptop_change": (
        "US",
        [
            intake("I just bought a laptop. Can I insure it?"),
            ("IDENTITY_INFO", identity_input("C", consent=False, with_dob=True)),
            ("OTP_CODE", {"code": "123456"}),
            needs("C"),
            ("DECISION", {"decision": "CHANGE", "text": "Actually the laptop cost $1,499."}),
            ("DECISION", {"decision": "ACCEPT"}),
            (
                "llm_reply",
                "PartiesExtraction",
                {
                    "all_self": False,
                    "parties": [{"role": "PAYER", "full_name": "Mary Doe", "date_of_birth": "1988-02-02"}],
                },
            ),
            ("PARTIES", {"text": "My wife Mary Doe (born 1988-02-02) pays."}),
            ("ANSWERS", {"text": "Serial SN-C-0001, order ORD-C-42, bought on Sept 10."}),
            ("CONFIRM", {"confirmed": True}),
        ],
    ),
    "d_identity_handoff_verified_needs_guard": (
        "US",
        [
            intake(),
            ("IDENTITY_INFO", identity_input("D", consent=True)),
            ("OTP_CODE", {"code": "000000"}),
            ("AGENT", {"resolution": "VERIFIED", "note": "Checked ID in person."}, "AGENT"),
            needs("D"),  # fills what to protect; the three after it add nothing and hand off
            needs("D"),
            needs("D"),
            needs("D"),
            ("AGENT", {"resolution": "CONTINUE"}, "AGENT"),
            needs("D"),
            needs("D"),
            needs("D"),
            ("AGENT", {"resolution": "END"}, "AGENT"),
        ],
    ),
    "d_identity_handoff_retry_identity": (
        "US",
        [
            intake("What's the weather like in Seattle?"),
            ("IDENTITY_INFO", identity_input("D", consent=False)),
            ("OTP_CODE", {"code": "000000"}),
            # identity starts over with the forms pre-filled (never the document number)
            ("AGENT", {"resolution": "CONTINUE"}, "AGENT"),
            identity_forms("D", consent=False)[0],
        ],
    ),
    "decline": (
        "KR",
        [
            intake(),
            ("IDENTITY_INFO", identity_input("A", consent=True)),
            needs("A"),
            ("DECISION", {"decision": "DECLINE"}),
        ],
    ),
    "no_eligible_product_handoff": (
        "KR",
        [
            intake(),
            ("IDENTITY_INFO", identity_input("A", consent=True)),
            # lives abroad: every KR product requires a KR resident
            ("llm_reply", "NeedsExtraction", {**NEEDS["A"], "residence_country": "JP"}),
            needs("A"),
            ("AGENT", {"resolution": "CONTINUE", "note": "Customer will reapply after moving back."}, "AGENT"),
            ("llm_reply", "NeedsExtraction", NEEDS["A"]),
            needs("A"),
        ],
    ),
    "answers_incomplete_handoff": (
        "KR",
        [
            intake(),
            ("IDENTITY_INFO", identity_input("B", consent=True)),
            ("OTP_CODE", {"code": CUSTOMERS["B"]["otp"]["valid_code"]}),
            needs("B"),
            ("DECISION", {"decision": "ACCEPT"}),
            ("PARTIES", {"text": "저 혼자 가요."}),
            ("llm_reply", "AnswersExtraction", {"answers": {}}),
            ("ANSWERS", {"text": "음..."}),
            ("ANSWERS", {"text": "잘 모르겠어요."}),
            ("ANSWERS", {"text": "나중에요."}),
            ("AGENT", {"resolution": "CONTINUE"}, "AGENT"),
            ("llm_reply", "AnswersExtraction", {"answers": ANSWERS["B"]}),
            ("ANSWERS", {"text": "1985년 11월 2일생 남자입니다."}),
        ],
    ),
    "kr_market_in_english": (
        "KR",
        [
            intake(),
            ("IDENTITY_INFO", identity_input("A", consent=True)),
            needs("A"),
            ("DECISION", {"decision": "ACCEPT"}),
            ("PARTIES", {"text": "I am the insured and I pay."}),
            ("CONFIRM", {"confirmed": True}),
        ],
        "en",
    ),
    "locale_switch_mid_session": (
        "KR",
        [
            intake(),
            ("IDENTITY_INFO", identity_input("B", consent=True)),
            ("OTP_CODE", {"code": CUSTOMERS["B"]["otp"]["valid_code"]}),
            ("locale", "en"),
            needs("B"),
            ("DECISION", {"decision": "ACCEPT"}),
            ("PARTIES", {"text": "Just me."}),
            ("locale", "ko"),
            ("ANSWERS", {"text": "1985년 11월 2일생 남자입니다."}),
            ("CONFIRM", {"confirmed": False, "text": "성별은 M이에요."}),
            ("CONFIRM", {"confirmed": True}),
        ],
    ),
    "errors_llm_handoff_and_contract_retry": (
        "KR",
        [
            intake(),
            ("IDENTITY_INFO", identity_input("A", consent=True)),
            ("fail", "llm", "assess_needs", 3),
            needs("A"),
            ("AGENT", {"resolution": "CONTINUE"}, "AGENT"),
            ("DECISION", {"decision": "ACCEPT"}),
            ("PARTIES", {"text": "me"}),
            ("fail", "external", "contract", 1),
            ("CONFIRM", {"confirmed": True}),
        ],
    ),
}


def normalize(value: Any) -> Any:
    """Replace ids (uuid4 per run) with a placeholder; everything else is deterministic under the fixed clock."""
    return json.loads(UUID.sub("<uuid>", json.dumps(value, ensure_ascii=False, default=str)))


def canonical_entities(entities: dict[str, Any]) -> dict[str, Any]:
    """Entity lists in content order: the fixed clock gives every row the same created_at, so the view's
    own order (created_at, rank) leaves ties between rounds unordered."""
    out = normalize(entities)
    for key, value in out.items():
        if isinstance(value, list):
            out[key] = sorted(value, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
    return out


def session_state(s) -> dict[str, Any]:
    fields = ("status", "last_stage", "waiting_for", "mode", "locale", "current_node")
    return {k: getattr(s, k) for k in fields}


async def node_path(rt, thread_id: str) -> list[str]:
    """Nodes in the order they were scheduled, from the checkpoint history (oldest first)."""
    history = [snap async for snap in rt.agent.graph.aget_state_history(rt.agent.config(thread_id))]
    return ["+".join(snap.next) or "(end)" for snap in reversed(history)]


async def transcript(rt, external, llm, market: str, steps: list[tuple], locale: str | None) -> dict[str, Any]:
    session, _ = await rt.create_session(market, locale)
    replies_in: list[str] = []  # the language each LLM call was told to reply in
    prompts: list[dict[str, Any]] = []  # every message each LLM call was sent, verbatim
    extract = llm.extract

    async def extract_and_record(node, schema, messages):
        replies_in.append(re.search(r"Reply in (\w+)", str(messages[0].content)).group(1))
        prompts.append({"node": node, "messages": [[m.type, str(m.content)] for m in messages]})
        return await extract(node, schema, messages)

    llm.extract = extract_and_record
    sid = str(session.session_id)
    seen = 0
    turns = []

    async def record(label: str) -> None:
        nonlocal seen
        s = await rt.get_session(sid)
        view = await rt.session_view(s)
        messages = [(m["role"], m["text"]) for m in view["messages"][seen:]]
        seen = len(view["messages"])
        turns.append({"input": label, "session": session_state(s), "messages": messages, "prompt": view["prompt"]})

    await record("(start)")
    for step in steps:
        if step[0] == "fail":
            _, system, target, n = step
            (llm if system == "llm" else external).fail[target] = n
            continue
        if step[0] == "llm_reply":
            _, schema, payload = step
            llm.overrides[schema] = payload
            continue
        if step[0] == "locale":
            await rt.set_locale(sid, step[1])
            continue
        input_type, data, *actor = step
        s = await rt.get_session(sid)
        await rt.submit_input(s, input_type, data, actor[0] if actor else "CUSTOMER")
        await rt.wait_idle(sid)
        await record(input_type)

    s = await rt.get_session(sid)
    return normalize(
        {
            "turns": turns,
            "node_path": await node_path(rt, s.thread_id),
            "entities": canonical_entities((await rt.session_detail(s))["entities"]),
            "llm_calls": [[*c, lang] for c, lang in zip(llm.calls, replies_in, strict=True)],
            "llm_prompts": prompts,
            "external_calls": [f"{method} {path}" for method, path, _headers, _body in external.calls],
        }
    )


@pytest.mark.parametrize("name", sorted(SCENARIOS))
async def test_golden_transcript(name, runtime, external, llm):
    market, steps, *locale = SCENARIOS[name]
    got = await transcript(runtime, external, llm, market, steps, locale[0] if locale else None)
    path = GOLDEN / f"{name}.json"
    if os.environ.get("UPDATE_GOLDEN"):
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n")
    assert path.exists(), f"no golden file; run with UPDATE_GOLDEN=1 to create {path.name}"
    assert got == json.loads(path.read_text())
