"""End-to-end graph scenarios for seed customers A-D (contracts/seed-customers.json), driven through
the Runtime with fake partner/identity/contract systems and a fake LLM."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import Application, NeedsAssessment, Party, Quote, Recommendation
from tests.fakes import CUSTOMERS, identity_input


async def send(rt, session_id: str, input_type: str, data: dict, actor: str = "CUSTOMER"):
    session = await rt.get_session(session_id)
    await rt.submit_input(session, input_type, data, actor)
    await rt.wait_idle(session_id)
    return await rt.get_session(session_id)


async def start(rt, market: str) -> str:
    session, _token = await rt.create_session(market)
    assert session.waiting_for == "IDENTITY_INFO"
    assert session.last_stage == "IDENTITY"
    return str(session.session_id)


async def party_of(rt, session_id: str) -> Party:
    session = await rt.get_session(session_id)
    async with rt.sessionmaker() as s:
        return await s.get(Party, session.party_id)


async def test_customer_a_partner_match_to_submission(runtime, external, llm):
    rt = runtime
    sid = await start(rt, "KR")
    s = await send(rt, sid, "IDENTITY_INFO", identity_input("A", consent=True))
    party = await party_of(rt, sid)
    assert party.verification_method == "PARTNER_MATCH" and party.verification_status == "VERIFIED"
    assert party.id_document_hmac and party.id_document_number_enc
    assert CUSTOMERS["A"]["id_document_number"].encode() not in party.id_document_number_enc
    # partner calls carry the consent header
    partner_calls = [c for c in external.calls if c[1].startswith("/partner")]
    assert partner_calls and all(c[2].get("x-consent-at") for c in partner_calls)
    assert s.waiting_for == "NEEDS" and s.last_stage == "PROFILING"

    s = await send(rt, sid, "NEEDS", {"text": CUSTOMERS["A"]["needs_text"]})
    assert s.waiting_for == "DECISION" and s.last_stage == "RECOMMENDATION"
    detail = await rt.session_detail(s)
    cards = detail["entities"]["recommendations"]
    assert len(cards) == 4  # all KR products recorded, ineligible ones with reasons
    eligible = [c for c in cards if c["eligibility_result"] == "ELIGIBLE"]
    assert [c["product_code"] for c in eligible] == ["KR-MOB-SWAP"]
    assert eligible[0]["rank"] == 1 and eligible[0]["rationale"] == "Fits you (A)."
    assert eligible[0]["quote"]["premium_minor"] == 9990  # MSRP tier <= 1.5M, purchase-price fallback
    assert all(c["failed_reasons"] for c in cards if c["eligibility_result"] == "INELIGIBLE")
    assert detail["prompt"]["options"][0]["recommendation_id"] == eligible[0]["recommendation_id"]

    s = await send(rt, sid, "DECISION", {"decision": "ACCEPT", "recommendation_id": eligible[0]["recommendation_id"]})
    assert s.waiting_for == "PARTIES" and s.last_stage == "APPLICATION"
    s = await send(rt, sid, "PARTIES", {"text": "제가 피보험자이자 납입자예요."})
    # all KR-MOB-SWAP answers are prefilled from the partner purchase -> straight to the summary
    assert s.waiting_for == "CONFIRM"
    view = await rt.session_view(s)
    assert view["prompt"]["summary"] == "Application summary for A."
    s = await send(rt, sid, "CONFIRM", {"confirmed": True})
    assert s.status == "SUBMITTED" and s.last_stage == "SUBMITTED" and s.waiting_for is None

    detail = await rt.session_detail(s)
    app = detail["entities"]["application"]
    assert app["status"] == "SUBMITTED" and app["submission_ref"].startswith("SUB-2026-")
    assert {p["role"] for p in detail["entities"]["application_parties"]} == {"POLICYHOLDER", "INSURED", "PAYER"}
    submit = [c for c in external.calls if c[1] == "/contract/v1/applications"]
    assert len(submit) == 1 and submit[0][2]["idempotency-key"] == app["application_id"]
    assert "id_document_number" not in str(submit[0][3]) and CUSTOMERS["A"]["phone"] not in str(submit[0][3])
    async with rt.sessionmaker() as db:
        rec = await db.get(Recommendation, uuid.UUID(eligible[0]["recommendation_id"]))
        assert rec.status == "ACCEPTED" and rec.decided_by == "CUSTOMER"
        quote = await db.get(Quote, uuid.UUID(eligible[0]["quote"]["quote_id"]))
        assert quote.status == "ACCEPTED"


async def test_customer_b_otp_travel_with_answers_loop(runtime, external):
    rt = runtime
    sid = await start(rt, "KR")
    s = await send(rt, sid, "IDENTITY_INFO", identity_input("B", consent=True))
    assert s.waiting_for == "OTP_CODE"
    s = await send(rt, sid, "OTP_CODE", {"code": CUSTOMERS["B"]["otp"]["valid_code"]})
    assert (await party_of(rt, sid)).verification_method == "OTP"
    assert s.waiting_for == "NEEDS"
    s = await send(rt, sid, "NEEDS", {"text": CUSTOMERS["B"]["needs_text"]})
    assert s.waiting_for == "DECISION"
    detail = await rt.session_detail(s)
    eligible = [c for c in detail["entities"]["recommendations"] if c["eligibility_result"] == "ELIGIBLE"]
    assert [c["product_code"] for c in eligible] == ["KR-TRV-OVERSEAS"]
    q = eligible[0]["quote"]
    assert q["premium_minor"] == 6750 and q["billing_period"] == "PER_TRIP"  # 5 days x 1,350
    assert (q["term_start_date"], q["term_end_date"]) == ("2026-10-03", "2026-10-07")
    assert q["valid_until"] == "2026-09-22T03:00:00Z"

    s = await send(rt, sid, "DECISION", {"decision": "ACCEPT", "recommendation_id": eligible[0]["recommendation_id"]})
    s = await send(rt, sid, "PARTIES", {"text": "저 혼자 가요."})
    assert s.waiting_for == "ANSWERS"
    detail = await rt.session_detail(s)
    assert set(detail["entities"]["application"]["missing_fields"]) == {"traveler_date_of_birth", "traveler_gender"}
    s = await send(rt, sid, "ANSWERS", {"text": "1985년 11월 2일생 남자입니다."})
    assert s.waiting_for == "CONFIRM"
    s = await send(rt, sid, "CONFIRM", {"confirmed": True})
    assert s.status == "SUBMITTED"


async def test_customer_c_otp_fails_document_succeeds(runtime):
    rt = runtime
    sid = await start(rt, "US")
    await send(rt, sid, "IDENTITY_INFO", identity_input("C", consent=False, with_dob=True))
    s = await send(rt, sid, "OTP_CODE", {"code": "123456"})
    party = await party_of(rt, sid)
    assert party.verification_method == "DOCUMENT" and party.verification_attempts == 1
    assert s.waiting_for == "NEEDS"
    s = await send(rt, sid, "NEEDS", {"text": CUSTOMERS["C"]["needs_text"]})
    detail = await rt.session_detail(s)
    eligible = [c for c in detail["entities"]["recommendations"] if c["eligibility_result"] == "ELIGIBLE"]
    assert [c["product_code"] for c in eligible] == ["US-DEV-LAPTOP-2Y"]
    assert eligible[0]["quote"]["premium_minor"] == 13000 and eligible[0]["quote"]["currency"] == "USD"
    device = detail["entities"]["insurable_objects"][0]["attributes"]
    assert device["device_category"] == "NOTEBOOK" and device["assumed_fields"] == [
        "condition",
        "has_existing_damage",
        "purchase_date",
    ]

    s = await send(rt, sid, "DECISION", {"decision": "ACCEPT", "recommendation_id": eligible[0]["recommendation_id"]})
    s = await send(rt, sid, "PARTIES", {"text": "Just me."})
    detail = await rt.session_detail(s)
    # the assumed purchase date is not copied into the application: it is asked for
    assert set(detail["entities"]["application"]["missing_fields"]) == {
        "purchase_date",
        "serial_number",
        "order_number",
    }
    s = await send(rt, sid, "ANSWERS", {"text": "Serial SN-C-0001, order ORD-C-42, bought on Sept 10."})
    assert s.waiting_for == "CONFIRM"
    s = await send(rt, sid, "CONFIRM", {"confirmed": True})
    detail = await rt.session_detail(s)
    answers = detail["entities"]["application"]["answers"]
    assert answers["order_number"] == "ORD-C-42" and answers["purchase_date"] == "2026-09-10"
    assert s.status == "SUBMITTED"


async def test_customer_d_double_failure_hands_off_then_agent_ends(runtime, external):
    rt = runtime
    sid = await start(rt, "US")
    await send(rt, sid, "IDENTITY_INFO", identity_input("D", consent=True))
    s = await send(rt, sid, "OTP_CODE", {"code": "000000"})
    party = await party_of(rt, sid)
    assert party.verification_attempts == 2 and party.verification_status == "FAILED"
    assert s.status == "HANDOFF" and s.waiting_for == "AGENT" and s.last_stage == "HANDOFF"
    # partner was consulted (consent) but did not match
    assert any(c[1] == "/partner/v1/customers/match" for c in external.calls)
    s = await send(
        rt, sid, "AGENT", {"resolution": "END", "note": "Asked the customer to visit a branch."}, actor="AGENT"
    )
    assert s.status == "WITHDRAWN" and s.waiting_for is None
    view = await rt.session_view(s)
    assert any(m["role"] == "agent" for m in view["messages"])


async def test_customer_d_agent_verifies_then_needs_loop_guard(runtime):
    rt = runtime
    sid = await start(rt, "US")
    await send(rt, sid, "IDENTITY_INFO", identity_input("D", consent=False))
    await send(rt, sid, "OTP_CODE", {"code": "999999"})
    s = await send(rt, sid, "AGENT", {"resolution": "VERIFIED"}, actor="AGENT")
    assert (await party_of(rt, sid)).verification_method == "AGENT"
    assert s.waiting_for == "NEEDS"
    for _ in range(2):
        s = await send(rt, sid, "NEEDS", {"text": CUSTOMERS["D"]["needs_text"]})
        assert s.waiting_for == "NEEDS"
    s = await send(rt, sid, "NEEDS", {"text": CUSTOMERS["D"]["needs_text"]})
    assert s.waiting_for == "AGENT" and s.status == "HANDOFF"  # guard after 3 rounds


async def test_change_creates_new_needs_version_and_expires_old(runtime):
    rt = runtime
    sid = await start(rt, "US")
    await send(rt, sid, "IDENTITY_INFO", identity_input("C", consent=False, with_dob=True))
    await send(rt, sid, "OTP_CODE", {"code": "1"})
    s = await send(rt, sid, "NEEDS", {"text": CUSTOMERS["C"]["needs_text"]})
    first = await rt.session_detail(s)
    first_ids = {c["recommendation_id"] for c in first["entities"]["recommendations"]}
    s = await send(rt, sid, "DECISION", {"decision": "CHANGE", "text": "Actually the laptop cost $1,499."})
    assert s.waiting_for == "DECISION"
    second = await rt.session_detail(s)
    assert second["entities"]["needs_assessment"]["version"] == 2
    old = [c for c in second["entities"]["recommendations"] if c["recommendation_id"] in first_ids]
    assert old and all(c["status"] == "EXPIRED" for c in old)
    new = [c for c in second["entities"]["recommendations"] if c["recommendation_id"] not in first_ids]
    assert new and all(c["status"] == "PROPOSED" for c in new)
    async with rt.sessionmaker() as db:
        versions = await db.scalar(select(func.count()).select_from(NeedsAssessment))
        assert versions >= 2
        old_quotes = (
            (await db.execute(select(Quote).where(Quote.recommendation_id.in_([uuid.UUID(i) for i in first_ids]))))
            .scalars()
            .all()
        )
        assert old_quotes and all(q.status == "EXPIRED" for q in old_quotes)


async def test_decline_ends_session(runtime):
    rt = runtime
    sid = await start(rt, "KR")
    await send(rt, sid, "IDENTITY_INFO", identity_input("A", consent=True))
    await send(rt, sid, "NEEDS", {"text": CUSTOMERS["A"]["needs_text"]})
    s = await send(rt, sid, "DECISION", {"decision": "DECLINE"})
    assert s.status == "DECLINED" and s.last_stage == "DECLINED" and s.waiting_for is None


async def test_llm_failure_exhausts_retries_and_hands_off_then_resumes(runtime, llm):
    rt = runtime
    sid = await start(rt, "KR")
    await send(rt, sid, "IDENTITY_INFO", identity_input("A", consent=True))
    llm.fail["assess_needs"] = 3  # == retry_max_attempts
    s = await send(rt, sid, "NEEDS", {"text": CUSTOMERS["A"]["needs_text"]})
    assert s.waiting_for == "AGENT" and s.status == "HANDOFF"
    values = (await rt.graph.aget_state(rt.config(s))).values
    assert values["last_error"]["node"] == "assess_needs" and values["handoff_reason"] == "ERROR"
    assert [c[0] for c in llm.calls].count("assess_needs") == 3
    # the agent lets the flow continue: the failed node re-runs and succeeds
    s = await send(rt, sid, "AGENT", {"resolution": "CONTINUE"}, actor="AGENT")
    assert s.waiting_for == "DECISION" and s.status == "ACTIVE"


async def test_transient_contract_failure_is_retried_idempotently(runtime, external):
    rt = runtime
    sid = await start(rt, "KR")
    await send(rt, sid, "IDENTITY_INFO", identity_input("A", consent=True))
    s = await send(rt, sid, "NEEDS", {"text": CUSTOMERS["A"]["needs_text"]})
    rec = (await rt.session_view(s))["prompt"]["options"][0]["recommendation_id"]
    await send(rt, sid, "DECISION", {"decision": "ACCEPT", "recommendation_id": rec})
    await send(rt, sid, "PARTIES", {"text": "me"})
    external.fail["contract"] = 1
    s = await send(rt, sid, "CONFIRM", {"confirmed": True})
    assert s.status == "SUBMITTED"
    async with rt.sessionmaker() as db:
        app = (await db.execute(select(Application).where(Application.session_id == uuid.UUID(sid)))).scalar_one()
        assert app.submission_ref == "SUB-2026-000001"
    assert len(external.submissions) == 1


async def test_input_type_must_match_waiting_for(runtime):
    import pytest

    from app.services.runtime import InputError

    rt = runtime
    sid = await start(rt, "KR")
    session = await rt.get_session(sid)
    with pytest.raises(InputError) as err:
        await rt.submit_input(session, "NEEDS", {"text": "hi"}, "CUSTOMER")
    assert err.value.status == 409
