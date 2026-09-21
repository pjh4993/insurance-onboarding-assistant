"""Routing functions read only the state (state-model.md §3), so they are tested without a DB."""

from __future__ import annotations

import pytest
from langgraph.graph import END

from onboarding_agent.build import ALL_NODES, EDGES, RETRYING_NODES, should_retry

ERR = {"last_error": {"node": "x", "kind": "ValueError", "attempts": 3}}


@pytest.mark.parametrize(
    ("fn", "state", "expected"),
    [
        (EDGES["ask_customer"], {"last_input": "IDENTITY_INFO"}, "verify_identity"),
        (EDGES["ask_customer"], {"last_input": "OTP_CODE"}, "check_otp"),
        (EDGES["ask_customer"], {"last_input": "NEEDS"}, "assess_needs"),
        (EDGES["ask_customer"], {"last_input": "PARTIES"}, "collect_parties"),
        (EDGES["ask_customer"], {"last_input": "ANSWERS"}, "collect_answers"),
        (EDGES["verify_identity"], {"identity_result": "MATCHED"}, "fetch_purchases"),
        (EDGES["verify_identity"], {"identity_result": "NOT_MATCHED"}, "ask_customer"),
        (EDGES["check_otp"], {"identity_result": "OTP_OK"}, "fetch_purchases"),
        (EDGES["check_otp"], {"identity_result": "OTP_FAILED"}, "check_document"),
        (EDGES["check_document"], {"identity_result": "DOC_OK"}, "fetch_purchases"),
        (EDGES["check_document"], {"identity_result": "DOC_FAILED"}, "human_handoff"),
        (EDGES["fetch_purchases"], {}, "assess_needs"),
        (EDGES["assess_needs"], {"needs_complete": False}, "ask_customer"),
        (EDGES["assess_needs"], {"needs_complete": True}, "check_eligibility"),
        (EDGES["assess_needs"], {"needs_complete": False, "handoff_reason": "NEEDS_INCOMPLETE"}, "human_handoff"),
        (EDGES["check_eligibility"], {"eligible_count": 0}, "human_handoff"),
        (EDGES["check_eligibility"], {"eligible_count": 2}, "rank_products"),
        (EDGES["rank_products"], {}, "quote_premium"),
        (EDGES["quote_premium"], {"eligible_count": 1}, "explain_recommendation"),
        (EDGES["quote_premium"], {"eligible_count": 0}, "human_handoff"),
        (EDGES["explain_recommendation"], {}, "await_decision"),
        (EDGES["await_decision"], {"decision": "ACCEPT"}, "open_application"),
        (EDGES["await_decision"], {"decision": "DECLINE"}, END),
        (EDGES["await_decision"], {"decision": "CHANGE"}, "assess_needs"),
        (EDGES["open_application"], {}, "collect_parties"),
        (EDGES["collect_parties"], {"parties_complete": False}, "ask_customer"),
        (EDGES["collect_parties"], {"parties_complete": True}, "collect_answers"),
        (EDGES["collect_answers"], {"answers_complete": False}, "ask_customer"),
        (EDGES["collect_answers"], {"answers_complete": True}, "summarize_application"),
        (EDGES["collect_answers"], {"handoff_reason": "ANSWERS_INCOMPLETE"}, "human_handoff"),
        (EDGES["summarize_application"], {}, "confirm_summary"),
        (EDGES["confirm_summary"], {"confirmed": True}, "submit_application"),
        (EDGES["confirm_summary"], {"confirmed": False}, "collect_answers"),
        (EDGES["submit_application"], {}, END),
        (EDGES["human_handoff"], {}, "await_agent"),
    ],
)
def test_routes(fn, state, expected):
    assert fn(state) == expected


@pytest.mark.parametrize("fn", [EDGES[n] for n in ALL_NODES if n not in ("human_handoff", "await_agent")])
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
    assert EDGES["await_agent"](state) == expected


def test_retry_predicate():
    import httpx

    req = httpx.Request("POST", "http://x")

    def status(code):
        return httpx.HTTPStatusError("e", request=req, response=httpx.Response(code, request=req))

    assert should_retry(status(500)) and should_retry(status(429))
    assert not should_retry(status(403)) and not should_retry(status(404))
    assert should_retry(httpx.ConnectTimeout("t")) and should_retry(ValueError("bad llm json"))
    assert not should_retry(KeyError("bug"))


def test_locale_of_falls_back_to_the_market_for_old_checkpoints():
    from onboarding_agent.texts import locale_of

    assert locale_of({"market": "KR"}) == "ko"
    assert locale_of({"market": "US"}) == "en"
    assert locale_of({"market": "KR", "locale": "en"}) == "en"


# In-flight sessions resume from checkpoints that name these nodes (`next`, `resume_node`), and the agent
# console shows them as `current_node`. Renaming or removing one breaks those sessions: migrate on purpose.
CHECKPOINTED_NODES = {
    "greet", "ask_customer", "verify_identity", "check_otp", "check_document", "fetch_purchases",
    "assess_needs", "check_eligibility", "rank_products", "quote_premium", "explain_recommendation",
    "await_decision", "open_application", "collect_parties", "collect_answers", "summarize_application",
    "confirm_summary", "submit_application", "human_handoff", "await_agent",
}  # fmt: skip


def test_node_names_are_stable():
    assert set(ALL_NODES) == CHECKPOINTED_NODES


def test_nodes_calling_the_llm_or_an_external_system_retry():
    assert set(RETRYING_NODES) == {
        "verify_identity",
        "check_otp",
        "check_document",
        "fetch_purchases",
        "assess_needs",
        "explain_recommendation",
        "collect_parties",
        "collect_answers",
        "summarize_application",
        "submit_application",
    }


def test_domain_registries_cover_the_state_vocabulary():
    from typing import get_args

    from onboarding_agent.flows import DOMAINS
    from onboarding_agent.flows.base import collect
    from onboarding_agent.state import HandoffReason, WaitingFor

    inputs, handoffs = collect(DOMAINS, "inputs"), collect(DOMAINS, "handoffs")
    # every free-form kind reaches a real node; the structured waits have their own nodes
    assert set(inputs) == set(get_args(WaitingFor)) - {"DECISION", "CONFIRM", "AGENT"}
    assert {kind.target for kind in inputs.values()} <= set(ALL_NODES)
    # every reason a node can raise has a resolution (ERROR is built into the handoff module)
    assert set(handoffs) | {"ERROR"} == set(get_args(HandoffReason))
    for reason, kind in handoffs.items():
        for resolution in ("VERIFIED", "CONTINUE"):
            assert kind.resume({"handoff_reason": reason, "handoff_resolution": resolution}) in ALL_NODES


def test_ask_customer_hands_off_an_unknown_kind_of_answer():
    assert EDGES["ask_customer"]({"last_input": "SOMETHING_ELSE"}) == "human_handoff"


def test_state_fields_are_stable():
    """State fields are checkpoint channels: like node names, renaming one strands in-flight sessions."""
    from typing import get_type_hints

    from onboarding_agent.state import OnboardingState, initial_state

    fields = set(get_type_hints(OnboardingState))
    assert fields == set(initial_state(session_id="s", party_id="p", market="KR", locale="ko"))
    assert fields == {
        "messages", "actor", "mode", "session_id", "party_id", "market", "locale", "stage", "waiting_for",
        "last_input",
        "identity_result", "otp_request_id", "otp_code",
        "needs_assessment_id", "insurable_object_ids", "needs_complete", "needs_rounds",
        "recommendation_ids", "quote_ids", "eligible_count", "decision",
        "application_id", "parties_complete", "answers_complete", "answers_rounds", "confirmed",
        "handoff_reason", "handoff_resolution", "resume_node", "resume_stage", "last_error",
    }  # fmt: skip
