"""Graph wiring (wiki/lifecycle.md §3). Every processing node has a conditional edge whose router
sends a populated `last_error` to `human_handoff`."""

from __future__ import annotations

import httpx
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from app.graph import routing as r
from app.graph.deps import Deps
from app.graph.nodes import Nodes
from app.graph.state import OnboardingState

# Nodes that call the LLM or an external system get a RetryPolicy (exponential backoff).
RETRYING_NODES = {
    "verify_identity",
    "check_otp",
    "check_document",
    "fetch_purchases",
    "submit_application",
    "assess_needs",
    "explain_recommendation",
    "collect_parties",
    "collect_answers",
    "summarize_application",
}

_PROGRAMMING_ERRORS = (AttributeError, KeyError, NameError, TypeError, LookupError, AssertionError)


def should_retry(exc: Exception) -> bool:
    """Retry transient failures (timeouts, 5xx, 429, malformed LLM output); not client errors or bugs."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code >= 500 or code == 429
    return not isinstance(exc, _PROGRAMMING_ERRORS)


EDGES = {
    "greet": r.after_greet,
    "ask_customer": r.after_ask_customer,
    "verify_identity": r.after_verify_identity,
    "check_otp": r.after_check_otp,
    "check_document": r.after_check_document,
    "fetch_purchases": r.after_fetch_purchases,
    "assess_needs": r.after_assess_needs,
    "check_eligibility": r.after_check_eligibility,
    "rank_products": r.after_rank_products,
    "quote_premium": r.after_quote_premium,
    "explain_recommendation": r.after_explain_recommendation,
    "await_decision": r.after_await_decision,
    "open_application": r.after_open_application,
    "collect_parties": r.after_collect_parties,
    "collect_answers": r.after_collect_answers,
    "summarize_application": r.after_summarize_application,
    "confirm_summary": r.after_confirm_summary,
    "submit_application": r.after_submit_application,
    "human_handoff": r.after_human_handoff,
    "await_agent": r.after_await_agent,
}

ALL_NODES = list(EDGES)


def build_graph(deps: Deps, checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph:
    nodes = Nodes(deps)
    retry = RetryPolicy(
        max_attempts=deps.settings.retry_max_attempts,
        initial_interval=deps.settings.retry_initial_interval,
        retry_on=should_retry,
    )
    g = StateGraph(OnboardingState)
    for name in ALL_NODES:
        g.add_node(name, getattr(nodes, name), retry_policy=retry if name in RETRYING_NODES else None)
    g.set_entry_point("greet")
    targets = [*ALL_NODES, END]
    for name, router in EDGES.items():
        g.add_conditional_edges(name, router, targets)
    return g.compile(checkpointer=checkpointer)
