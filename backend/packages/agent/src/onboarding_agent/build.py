"""Graph wiring (wiki/lifecycle.md §3): one flat graph assembled from the domain modules in
`onboarding_agent.flows`. Every processing node has a conditional edge whose router sends a populated
`last_error` to `human_handoff`."""

from __future__ import annotations

import httpx
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from onboarding_agent.deps import AgentDeps
from onboarding_agent.flows import DOMAINS
from onboarding_agent.state import OnboardingState

# Nodes that call the LLM or an external system get a RetryPolicy (exponential backoff).
RETRYING_NODES = frozenset().union(*(d.retrying for d in DOMAINS))

_PROGRAMMING_ERRORS = (AttributeError, KeyError, NameError, TypeError, LookupError, AssertionError)


def should_retry(exc: Exception) -> bool:
    """Retry transient failures (timeouts, 5xx, 429, malformed LLM output); not client errors or bugs."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code >= 500 or code == 429
    return not isinstance(exc, _PROGRAMMING_ERRORS)


EDGES = {name: router for d in DOMAINS for name, router in d.edges.items()}

ALL_NODES = list(EDGES)


def build_graph(deps: AgentDeps, checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph:
    nodes = {name: fn for d in DOMAINS for name, fn in d.nodes(deps).items()}
    retry = RetryPolicy(
        max_attempts=deps.config.retry_max_attempts,
        initial_interval=deps.config.retry_initial_interval,
        retry_on=should_retry,
    )
    g = StateGraph(OnboardingState)
    for name in ALL_NODES:
        g.add_node(name, nodes[name], retry_policy=retry if name in RETRYING_NODES else None)
    g.set_entry_point("greet")
    targets = [*ALL_NODES, END]
    for name, router in EDGES.items():
        g.add_conditional_edges(name, router, targets)
    return g.compile(checkpointer=checkpointer)
