"""Conditional-edge functions (wiki/state-model.md §3). They read only the state — never the DB —
so a branch can be replayed from the checkpoint alone and tested without a database."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END

HANDOFF = "human_handoff"

_INPUT_TARGET = {
    "IDENTITY_INFO": "verify_identity",
    "OTP_CODE": "check_otp",
    "NEEDS": "assess_needs",
    "PARTIES": "collect_parties",
    "ANSWERS": "collect_answers",
}


def _error(state: dict[str, Any]) -> bool:
    return bool(state.get("last_error"))


def after_greet(state: dict[str, Any]) -> str:
    return HANDOFF if _error(state) else "ask_customer"


def after_ask_customer(state: dict[str, Any]) -> str:
    if _error(state):
        return HANDOFF
    return _INPUT_TARGET.get(state.get("last_input") or "", HANDOFF)


def after_verify_identity(state: dict[str, Any]) -> str:
    if _error(state):
        return HANDOFF
    return "fetch_purchases" if state.get("identity_result") == "MATCHED" else "ask_customer"


def after_check_otp(state: dict[str, Any]) -> str:
    if _error(state):
        return HANDOFF
    return "fetch_purchases" if state.get("identity_result") == "OTP_OK" else "check_document"


def after_check_document(state: dict[str, Any]) -> str:
    if _error(state):
        return HANDOFF
    return "fetch_purchases" if state.get("identity_result") == "DOC_OK" else HANDOFF


def after_fetch_purchases(state: dict[str, Any]) -> str:
    return HANDOFF if _error(state) else "assess_needs"


def after_assess_needs(state: dict[str, Any]) -> str:
    if _error(state) or state.get("handoff_reason") == "NEEDS_INCOMPLETE":
        return HANDOFF
    return "check_eligibility" if state.get("needs_complete") else "ask_customer"


def after_check_eligibility(state: dict[str, Any]) -> str:
    if _error(state) or state.get("eligible_count", 0) == 0:
        return HANDOFF
    return "rank_products"


def after_rank_products(state: dict[str, Any]) -> str:
    return HANDOFF if _error(state) else "quote_premium"


def after_quote_premium(state: dict[str, Any]) -> str:
    if _error(state) or state.get("eligible_count", 0) == 0:
        return HANDOFF
    return "explain_recommendation"


def after_explain_recommendation(state: dict[str, Any]) -> str:
    return HANDOFF if _error(state) else "await_decision"


def after_await_decision(state: dict[str, Any]) -> str:
    if _error(state):
        return HANDOFF
    decision = state.get("decision")
    if decision == "ACCEPT":
        return "open_application"
    if decision == "CHANGE":
        return "assess_needs"
    return END


def after_open_application(state: dict[str, Any]) -> str:
    return HANDOFF if _error(state) else "collect_parties"


def after_collect_parties(state: dict[str, Any]) -> str:
    if _error(state):
        return HANDOFF
    return "collect_answers" if state.get("parties_complete") else "ask_customer"


def after_collect_answers(state: dict[str, Any]) -> str:
    if _error(state) or state.get("handoff_reason") == "ANSWERS_INCOMPLETE":
        return HANDOFF
    return "summarize_application" if state.get("answers_complete") else "ask_customer"


def after_summarize_application(state: dict[str, Any]) -> str:
    return HANDOFF if _error(state) else "confirm_summary"


def after_confirm_summary(state: dict[str, Any]) -> str:
    if _error(state):
        return HANDOFF
    return "submit_application" if state.get("confirmed") else "collect_answers"


def after_submit_application(state: dict[str, Any]) -> str:
    return HANDOFF if _error(state) else END


def after_human_handoff(state: dict[str, Any]) -> str:
    return "await_agent"


def after_await_agent(state: dict[str, Any]) -> str:
    """Where an agent's resolution sends the session."""
    resolution = state.get("handoff_resolution")
    reason = state.get("handoff_reason")
    if resolution == "END":
        return END
    if reason == "IDENTITY_FAILED":
        return "fetch_purchases" if resolution == "VERIFIED" else "greet"
    if reason in ("NO_ELIGIBLE_PRODUCT", "NEEDS_INCOMPLETE"):
        return "assess_needs"
    if reason == "ANSWERS_INCOMPLETE":
        return "collect_answers"
    if reason == "ERROR" and state.get("resume_node"):
        return state["resume_node"]
    return END
