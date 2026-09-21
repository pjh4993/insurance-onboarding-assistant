"""Routing functions read only the state (state-model.md §3), so they are tested without a DB."""

from __future__ import annotations

import pytest
from langgraph.graph import END

from onboarding_agent import routing as r
from onboarding_agent.build import ALL_NODES, should_retry

ERR = {"last_error": {"node": "x", "kind": "ValueError", "attempts": 3}}


@pytest.mark.parametrize(
    ("fn", "state", "expected"),
    [
        (r.after_ask_customer, {"last_input": "IDENTITY_INFO"}, "verify_identity"),
        (r.after_ask_customer, {"last_input": "OTP_CODE"}, "check_otp"),
        (r.after_ask_customer, {"last_input": "NEEDS"}, "assess_needs"),
        (r.after_ask_customer, {"last_input": "PARTIES"}, "collect_parties"),
        (r.after_ask_customer, {"last_input": "ANSWERS"}, "collect_answers"),
        (r.after_verify_identity, {"identity_result": "MATCHED"}, "fetch_purchases"),
        (r.after_verify_identity, {"identity_result": "NOT_MATCHED"}, "ask_customer"),
        (r.after_check_otp, {"identity_result": "OTP_OK"}, "fetch_purchases"),
        (r.after_check_otp, {"identity_result": "OTP_FAILED"}, "check_document"),
        (r.after_check_document, {"identity_result": "DOC_OK"}, "fetch_purchases"),
        (r.after_check_document, {"identity_result": "DOC_FAILED"}, "human_handoff"),
        (r.after_fetch_purchases, {}, "assess_needs"),
        (r.after_assess_needs, {"needs_complete": False}, "ask_customer"),
        (r.after_assess_needs, {"needs_complete": True}, "check_eligibility"),
        (r.after_assess_needs, {"needs_complete": False, "handoff_reason": "NEEDS_INCOMPLETE"}, "human_handoff"),
        (r.after_check_eligibility, {"eligible_count": 0}, "human_handoff"),
        (r.after_check_eligibility, {"eligible_count": 2}, "rank_products"),
        (r.after_rank_products, {}, "quote_premium"),
        (r.after_quote_premium, {"eligible_count": 1}, "explain_recommendation"),
        (r.after_quote_premium, {"eligible_count": 0}, "human_handoff"),
        (r.after_explain_recommendation, {}, "await_decision"),
        (r.after_await_decision, {"decision": "ACCEPT"}, "open_application"),
        (r.after_await_decision, {"decision": "DECLINE"}, END),
        (r.after_await_decision, {"decision": "CHANGE"}, "assess_needs"),
        (r.after_open_application, {}, "collect_parties"),
        (r.after_collect_parties, {"parties_complete": False}, "ask_customer"),
        (r.after_collect_parties, {"parties_complete": True}, "collect_answers"),
        (r.after_collect_answers, {"answers_complete": False}, "ask_customer"),
        (r.after_collect_answers, {"answers_complete": True}, "summarize_application"),
        (r.after_collect_answers, {"handoff_reason": "ANSWERS_INCOMPLETE"}, "human_handoff"),
        (r.after_summarize_application, {}, "confirm_summary"),
        (r.after_confirm_summary, {"confirmed": True}, "submit_application"),
        (r.after_confirm_summary, {"confirmed": False}, "collect_answers"),
        (r.after_submit_application, {}, END),
        (r.after_human_handoff, {}, "await_agent"),
    ],
)
def test_routes(fn, state, expected):
    assert fn(state) == expected


@pytest.mark.parametrize(
    "fn", [getattr(r, f"after_{n}") for n in ALL_NODES if n not in ("human_handoff", "await_agent")]
)
def test_every_router_sends_last_error_to_handoff(fn):
    assert (
        fn(
            {
                **ERR,
                "identity_result": "MATCHED",
                "needs_complete": True,
                "eligible_count": 3,
                "decision": "ACCEPT",
                "confirmed": True,
                "last_input": "NEEDS",
            }
        )
        == "human_handoff"
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"handoff_resolution": "END", "handoff_reason": "IDENTITY_FAILED"}, END),
        ({"handoff_resolution": "VERIFIED", "handoff_reason": "IDENTITY_FAILED"}, "fetch_purchases"),
        ({"handoff_resolution": "CONTINUE", "handoff_reason": "IDENTITY_FAILED"}, "greet"),
        ({"handoff_resolution": "CONTINUE", "handoff_reason": "NO_ELIGIBLE_PRODUCT"}, "assess_needs"),
        ({"handoff_resolution": "CONTINUE", "handoff_reason": "NEEDS_INCOMPLETE"}, "assess_needs"),
        ({"handoff_resolution": "CONTINUE", "handoff_reason": "ANSWERS_INCOMPLETE"}, "collect_answers"),
        (
            {"handoff_resolution": "CONTINUE", "handoff_reason": "ERROR", "resume_node": "submit_application"},
            "submit_application",
        ),
        ({"handoff_resolution": "VERIFIED", "handoff_reason": "ERROR", "resume_node": "assess_needs"}, "assess_needs"),
    ],
)
def test_after_await_agent(state, expected):
    assert r.after_await_agent(state) == expected


def test_retry_predicate():
    import httpx

    req = httpx.Request("POST", "http://x")

    def status(code):
        return httpx.HTTPStatusError("e", request=req, response=httpx.Response(code, request=req))

    assert should_retry(status(500)) and should_retry(status(429))
    assert not should_retry(status(403)) and not should_retry(status(404))
    assert should_retry(httpx.ConnectTimeout("t")) and should_retry(ValueError("bad llm json"))
    assert not should_retry(KeyError("bug"))
