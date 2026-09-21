"""The intake turn and the small forms: what the first reply says, identity asked topic by topic, needs asked
topic by topic (fields merged without the LLM), and the form each prompt carries."""

from __future__ import annotations

import uuid

from app.db.models import NeedsAssessment, Party
from tests.fakes import CUSTOMERS, INTAKE_OFF_TOPIC, INTAKE_ON_TOPIC, identity_input
from tests.test_scenarios import send, start


async def prompt_of(rt, sid: str) -> dict:
    return (await rt.session_view(await rt.get_session(sid)))["prompt"]


async def values_of(rt, sid: str) -> dict:
    return (await rt.agent.snapshot((await rt.get_session(sid)).thread_id)).values


async def new_session(rt, market: str) -> str:
    session, _ = await rt.create_session(market)
    return str(session.session_id)


def names(form: dict) -> list[tuple[str, bool]]:
    return [(f["name"], f["required"]) for f in form["fields"]]


async def to_needs(rt, key: str) -> str:
    """A KR session for seed customer `key` (B: OTP, no partner record), waiting for its first needs form."""
    sid = await start(rt, "KR")
    await send(rt, sid, "IDENTITY_INFO", identity_input(key, consent=False))
    s = await send(rt, sid, "OTP_CODE", {"code": CUSTOMERS[key]["otp"]["valid_code"]})
    assert s.waiting_for == "NEEDS"
    return sid


# ------------------------------------------------------------------------------------------ intake


async def test_intake_answers_an_insurance_question_and_notes_the_product(runtime, llm):
    rt = runtime
    sid = await new_session(rt, "KR")
    prompt = await prompt_of(rt, sid)
    assert prompt["waiting_for"] == "INTAKE" and "form" not in prompt

    s = await send(rt, sid, "INTAKE", {"text": "휴대폰 액정이 깨지면 보험으로 되나요?"})
    assert s.waiting_for == "IDENTITY_INFO"
    messages = (await rt.session_view(s))["messages"]
    assert messages[1] == {**messages[1], "role": "customer", "text": "휴대폰 액정이 깨지면 보험으로 되나요?"}
    reply = messages[2]["text"]
    assert reply.startswith(INTAKE_ON_TOPIC) and "본인 확인" in reply  # answers, then says what comes next
    assert [c[:2] for c in llm.calls] == [("understand_intake", "IntakeReply")]
    values = await values_of(rt, sid)
    assert values["product_interest"] == "MOBILE_INSURANCE"
    assert values["intake"] == {"text": "휴대폰 액정이 깨지면 보험으로 되나요?"}


async def test_intake_off_topic_says_what_the_assistant_is_for(runtime):
    rt = runtime
    sid = await new_session(rt, "US")
    s = await send(rt, sid, "INTAKE", {"text": "Who won the game last night?"})
    reply = (await rt.session_view(s))["messages"][2]["text"]
    assert reply.startswith(INTAKE_OFF_TOPIC) and "verify your identity" in reply
    assert (await values_of(rt, sid))["product_interest"] is None


async def test_an_empty_intake_opens_without_the_llm(runtime, llm):
    rt = runtime
    sid = await new_session(rt, "US")
    s = await send(rt, sid, "INTAKE", {"text": ""})
    view = await rt.session_view(s)
    assert [m["role"] for m in view["messages"]] == ["assistant", "assistant", "assistant"]  # no empty bubble
    assert view["messages"][1]["text"].startswith("Great, let's get started.")
    assert llm.calls == []
    assert view["prompt"]["form"]["topic"] == "contact"


async def test_an_intake_llm_failure_hands_off_and_resumes(runtime, llm):
    rt = runtime
    sid = await new_session(rt, "KR")
    llm.fail["understand_intake"] = 3
    s = await send(rt, sid, "INTAKE", {"text": "여행자보험 있나요?"})
    assert s.status == "HANDOFF" and s.waiting_for == "AGENT"
    s = await send(rt, sid, "AGENT", {"resolution": "CONTINUE"}, actor="AGENT")
    assert s.waiting_for == "IDENTITY_INFO" and s.last_stage == "IDENTITY"
    assert (await values_of(rt, sid))["product_interest"] == "TRAVEL_PROTECTION"


# ------------------------------------------------------------------------------------------ identity


async def test_identity_by_topics_merges_partial_answers(runtime, settings):
    rt = runtime
    c = CUSTOMERS["B"]
    sid = await start(rt, "KR")
    prompt = await prompt_of(rt, sid)
    assert prompt["form"]["topic"] == "contact" and not prompt["form"]["allow_text"]
    assert names(prompt["form"]) == [("full_name", True), ("email", True), ("phone", True)]

    contact = {k: c[k] for k in ("full_name", "email", "phone")}
    s = await send(rt, sid, "IDENTITY_INFO", {"topic": "contact", "fields": contact})
    assert s.waiting_for == "IDENTITY_INFO"
    form = (await prompt_of(rt, sid))["form"]
    assert form["topic"] == "id_document"
    assert form["fields"][0]["options"][1] == {"value": "PASSPORT", "label": "여권"}

    document = {"id_document_type": c["id_document_type"], "id_document_number": c["id_document_number"]}
    s = await send(rt, sid, "IDENTITY_INFO", {"topic": "id_document", "fields": document})
    form = (await prompt_of(rt, sid))["form"]
    assert form["topic"] == "consent" and names(form) == [("third_party_consent", True)]
    assert "제휴 판매처" in form["reason"]

    s = await send(rt, sid, "IDENTITY_INFO", {"topic": "consent", "fields": {"third_party_consent": True}})
    assert s.waiting_for == "OTP_CODE"  # all three in: verification runs as before (B has no partner record)
    async with rt.sessionmaker() as db:
        party = await db.get(Party, s.party_id)
    assert (party.full_name, party.email, party.phone) == (c["full_name"], c["email"], c["phone"])
    assert party.id_document_type == "NATIONAL_ID" and party.id_document_hmac
    assert c["id_document_number"].encode() not in party.id_document_number_enc
    assert party.third_party_consent_at is not None

    # every form became a readable customer message; the document number is masked
    customer = [m["text"] for m in (await rt.session_view(s))["messages"] if m["role"] == "customer"]
    assert customer[0] == f"이름: {c['full_name']} · 이메일: {c['email']} · 휴대폰 번호: {c['phone']}"
    assert customer[1] == "신분증 종류: 주민등록증 · 신분증 번호: ************02"
    assert customer[2] == "파트너사 정보 조회 동의: 동의"
    assert c["id_document_number"] not in str(await rt.session_detail(s))


async def test_identity_topics_in_any_order_ask_only_what_is_left(runtime):
    rt = runtime
    sid = await start(rt, "US")
    s = await send(rt, sid, "IDENTITY_INFO", {"topic": "consent", "fields": {"third_party_consent": False}})
    assert (await prompt_of(rt, sid))["form"]["topic"] == "contact"
    fields = {k: CUSTOMERS["C"][k] for k in ("full_name", "email", "phone")}
    s = await send(rt, sid, "IDENTITY_INFO", {"topic": "contact", "fields": fields})
    assert (await prompt_of(rt, sid))["form"]["topic"] == "id_document"
    assert (await values_of(rt, sid))["identity_topics"] == ["contact", "consent"]
    assert s.waiting_for == "IDENTITY_INFO"


async def test_the_full_shape_still_goes_straight_to_verification(runtime):
    rt = runtime
    sid = await start(rt, "KR")
    s = await send(rt, sid, "IDENTITY_INFO", identity_input("A", consent=True))
    assert s.waiting_for == "NEEDS" and s.last_stage == "PROFILING"  # partner match, no forms in between
    assert (await values_of(rt, sid))["identity_topics"] == ["contact", "id_document", "consent"]


async def test_identity_retry_prefills_the_forms_but_never_the_document_number(runtime):
    rt = runtime
    c = CUSTOMERS["D"]
    sid = await start(rt, "US")
    await send(rt, sid, "IDENTITY_INFO", identity_input("D", consent=True))
    s = await send(rt, sid, "OTP_CODE", {"code": "000000"})
    assert s.status == "HANDOFF"
    s = await send(rt, sid, "AGENT", {"resolution": "CONTINUE"}, actor="AGENT")
    assert s.waiting_for == "IDENTITY_INFO"
    form = (await prompt_of(rt, sid))["form"]
    assert {f["name"]: f.get("value") for f in form["fields"]} == {
        "full_name": c["full_name"],
        "email": c["email"],
        "phone": c["phone"],
    }
    await send(
        rt, sid, "IDENTITY_INFO", {"topic": "contact", "fields": {k: c[k] for k in ("full_name", "email", "phone")}}
    )
    form = (await prompt_of(rt, sid))["form"]
    assert {f["name"]: f.get("value") for f in form["fields"]} == {
        "id_document_type": "DRIVER_LICENSE",
        "id_document_number": None,
    }
    await send(
        rt,
        sid,
        "IDENTITY_INFO",
        {"topic": "id_document", "fields": {"id_document_type": "DRIVER_LICENSE", "id_document_number": "X1"}},
    )
    form = (await prompt_of(rt, sid))["form"]
    assert form["fields"][0]["value"] is True  # consent was given the first time


# ------------------------------------------------------------------------------------------ needs


async def test_needs_by_topic_merge_without_the_llm(runtime, llm):
    rt = runtime
    sid = await to_needs(rt, "B")
    llm.calls.clear()
    form = (await prompt_of(rt, sid))["form"]
    assert form["topic"] == "coverage" and form["allow_text"]
    assert names(form) == [("objectives", True)] and "value" not in form["fields"][0]

    s = await send(rt, sid, "NEEDS", {"topic": "coverage", "fields": {"objectives": ["PROTECT_DEVICE"]}})
    prompt = await prompt_of(rt, sid)
    assert prompt["message"] == "감사합니다! 고객님에 대해 조금 알려 주세요."  # no product interest: the person next
    s = await send(
        rt, sid, "NEEDS", {"topic": "person", "fields": {"age_range": "AGE_40_49", "residence_country": "kr"}}
    )
    form = (await prompt_of(rt, sid))["form"]
    assert form["topic"] == "device"
    assert names(form) == [
        ("device_category", True),
        ("manufacturer", False),
        ("model", False),
        ("purchase_date", False),
        ("purchase_price", True),
    ]
    assert form["fields"][-1]["label"] == "구매 가격 (KRW)"

    # a phone's maker decides eligibility: the device form comes back with the maker required, pre-filled
    s = await send(
        rt, sid, "NEEDS", {"topic": "device", "fields": {"device_category": "SMARTPHONE", "purchase_price": 1350000}}
    )
    form = (await prompt_of(rt, sid))["form"]
    assert form["topic"] == "device" and ("manufacturer", True) in names(form)
    assert {f["name"]: f.get("value") for f in form["fields"]}["purchase_price"] == 1350000

    s = await send(rt, sid, "NEEDS", {"topic": "device", "fields": {"manufacturer": "삼성", "model": "Galaxy S26"}})
    assert s.waiting_for == "DECISION"  # four forms in a row do not trip the loop guard
    assert llm.calls and all(c[0] != "assess_needs" for c in llm.calls)
    values = await values_of(rt, sid)
    async with rt.sessionmaker() as db:
        na = await db.get(NeedsAssessment, uuid.UUID(values["needs_assessment_id"]))
    assert (na.age_range, na.residence_country, na.objectives) == ("AGE_40_49", "KR", ["PROTECT_DEVICE"])
    assert na.device == {
        "device_category": "SMARTPHONE",
        "purchase_price_minor": 1350000,
        "manufacturer": "Samsung",
        "model": "Galaxy S26",
    }
    customer = [m["text"] for m in (await rt.session_view(s))["messages"] if m["role"] == "customer"]
    assert "기기 종류: 스마트폰 · 구매 가격: ₩1,350,000" in customer


async def test_needs_forms_follow_the_product_interest(runtime):
    rt = runtime
    sid = await start(rt, "US", intake="Do you have travel insurance?")
    await send(rt, sid, "IDENTITY_INFO", identity_input("C", consent=False, with_dob=True))
    s = await send(rt, sid, "OTP_CODE", {"code": "1"})
    assert s.waiting_for == "NEEDS"
    form = (await prompt_of(rt, sid))["form"]
    assert form["topic"] == "coverage" and form["fields"][0]["value"] == ["TRAVEL_COVER"]
    await send(rt, sid, "NEEDS", {"topic": "coverage", "fields": {"objectives": ["TRAVEL_COVER"]}})
    form = (await prompt_of(rt, sid))["form"]
    assert form["topic"] == "trip"  # the line the customer came for, before the person
    assert names(form) == [
        ("destination_countries", True),
        ("departure_date", True),
        ("return_date", True),
        ("trip_cost", True),  # US trip cover is rated on the trip cost
    ]
    await send(
        rt,
        sid,
        "NEEDS",
        {
            "topic": "trip",
            "fields": {
                "destination_countries": ["jp"],
                "departure_date": "2026-10-03",
                "return_date": "2026-10-07",
                "trip_cost": 2500,
            },
        },
    )
    values = await values_of(rt, sid)
    async with rt.sessionmaker() as db:
        na = await db.get(NeedsAssessment, uuid.UUID(values["needs_assessment_id"]))
    assert na.trip["trip_cost_minor"] == 250000 and na.trip["destination_countries"] == ["JP"]
    assert (await prompt_of(rt, sid))["form"]["topic"] == "person"


async def test_needs_text_and_fields_together_the_fields_win(runtime, llm):
    rt = runtime
    sid = await to_needs(rt, "B")
    s = await send(
        rt,
        sid,
        "NEEDS",
        {"topic": "person", "fields": {"age_range": "AGE_50_64"}, "text": CUSTOMERS["B"]["needs_text"]},
    )
    assert [c[0] for c in llm.calls].count("assess_needs") == 1
    assert s.waiting_for == "DECISION"
    values = await values_of(rt, sid)
    async with rt.sessionmaker() as db:
        na = await db.get(NeedsAssessment, uuid.UUID(values["needs_assessment_id"]))
    assert na.age_range == "AGE_50_64" and na.objectives == ["TRAVEL_COVER"]  # the rest came from the text
    customer = [m["text"] for m in (await rt.session_view(s))["messages"] if m["role"] == "customer"]
    assert customer[-1] == f"나이대: 50–64세\n{CUSTOMERS['B']['needs_text']}"


async def test_the_intake_text_feeds_the_needs_extraction(runtime, llm):
    rt = runtime
    sid = await start(rt, "KR", intake="갤럭시 폰 보험 알아보는 중이에요")
    await send(rt, sid, "IDENTITY_INFO", identity_input("B", consent=False))
    await send(rt, sid, "OTP_CODE", {"code": CUSTOMERS["B"]["otp"]["valid_code"]})
    prompts: list[str] = []
    extract = llm.extract

    async def spy(node, schema, messages):
        if node == "assess_needs":
            prompts.append(str(messages[-1].content))
        return await extract(node, schema, messages)

    llm.extract = spy
    await send(rt, sid, "NEEDS", {"text": "마흔 살이에요."})
    assert prompts == ["갤럭시 폰 보험 알아보는 중이에요\n\n마흔 살이에요."]


async def test_needs_loop_guard_hands_off_when_answers_add_nothing(runtime, llm):
    rt = runtime
    sid = await to_needs(rt, "B")
    llm.overrides["NeedsExtraction"] = {}  # the customer's replies say nothing usable
    for _ in range(2):
        s = await send(rt, sid, "NEEDS", {"text": "음..."})
        assert s.waiting_for == "NEEDS" and (await prompt_of(rt, sid))["form"]["topic"] == "coverage"
    # a form that fills nothing counts too
    s = await send(rt, sid, "NEEDS", {"topic": "person", "fields": {"occupation": "회사원"}})
    assert s.waiting_for == "AGENT" and s.status == "HANDOFF"
    assert (await values_of(rt, sid))["handoff_reason"] == "NEEDS_INCOMPLETE"


async def test_prompt_forms_only_on_identity_and_needs(runtime):
    rt = runtime
    sid = await start(rt, "KR")
    await send(rt, sid, "IDENTITY_INFO", identity_input("A", consent=True))
    await send(rt, sid, "NEEDS", {"text": CUSTOMERS["A"]["needs_text"]})
    prompt = await prompt_of(rt, sid)
    assert prompt["waiting_for"] == "DECISION" and "form" not in prompt and prompt["options"]


async def test_sse_prompt_updates_carry_the_form(runtime):
    rt = runtime
    events = []
    publish = rt.broker.publish

    async def capture(event):
        events.append(event)
        await publish(event)

    rt.broker.publish = capture
    sid = await new_session(rt, "US")
    await send(rt, sid, "INTAKE", {"text": ""})
    prompts = [e.data["prompt"] for e in events if e.type == "prompt.updated"]
    assert "form" not in prompts[0] and prompts[-1]["form"]["topic"] == "contact"
