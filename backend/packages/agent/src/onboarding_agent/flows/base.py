"""What every domain flow shares: its dependencies, the clock, the session party, the LLM system prompt,
and the `DomainModule` contract `build.py` assembles the graph from.

- code nodes decide and compute: verify_identity, check_otp, check_document, fetch_purchases,
  check_eligibility, rank_products, quote_premium, open_application, submit_application
- LLM nodes extract or write: assess_needs, explain_recommendation, collect_parties,
  collect_answers, summarize_application
- wait nodes stop on `interrupt()`: ask_customer, await_decision, confirm_summary, await_agent

A node that needs customer input sets `waiting_for` and appends the question, then routes to
`ask_customer`, which interrupts and records the answer. Nodes reach the domain DB only through the
`UnitOfWork` port. Every write is idempotent: new rows get `uuid5(thread_id, node, step)` ids and are
upserted with `save`."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from onboarding_agent.deps import AgentDeps
from onboarding_agent.texts import locale_of
from onboarding_core.party.models import Party
from onboarding_core.ports import UnitOfWork

NodeFn = Callable[[dict[str, Any], RunnableConfig], Awaitable[dict[str, Any]]]
Router = Callable[[dict[str, Any]], str]


def thread_of(config: RunnableConfig) -> str:
    return config["configurable"]["thread_id"]


def step_of(config: RunnableConfig) -> int:
    return int(config.get("metadata", {}).get("langgraph_step", 0))


def as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def latest_texts(messages: list[BaseMessage], input_types: tuple[str, ...]) -> list[str]:
    return [
        str(m.content)
        for m in messages
        if isinstance(m, HumanMessage) and m.additional_kwargs.get("input_type") in input_types
    ]


class Flow:
    def __init__(self, deps: AgentDeps) -> None:
        self.d = deps

    def now(self) -> datetime:
        return self.d.clock()

    async def _touch(self, state: dict[str, Any], entity_type: str, entity_id: Any) -> None:
        await self.d.on_entity(state["session_id"], entity_type, str(entity_id))

    async def _party(self, uow: UnitOfWork, state: dict[str, Any]) -> Party:
        party = await uow.parties.get(as_uuid(state["party_id"]))
        if party is None:
            raise LookupError("session party not found")
        return party

    def _system(self, state: dict[str, Any], party: Party, instructions: str) -> SystemMessage:
        market = state["market"]
        language = "Korean" if locale_of(state) == "ko" else "English"
        return SystemMessage(
            content=(
                "You are the onboarding assistant of an insurance company.\n"
                f"Customer: {party.full_name or 'unknown'}\n"
                f"Market: {market}. Reply in {language}. Today is {self.now().date().isoformat()}.\n"
                "Money is in integer minor units (KRW won, USD cents).\n\n"
                f"{instructions}"
            )
        )


# Stores a free-form answer of one kind: (flow, state, value, now) -> (transcript text, state updates).
InputRecorder = Callable[["Flow", dict[str, Any], dict[str, Any], datetime], Awaitable[tuple[str, dict[str, Any]]]]
# Applies an agent's resolution of one handoff reason: (flow, state, resolution, now) -> (messages, updates).
HandoffResolver = Callable[
    ["Flow", dict[str, Any], str | None, datetime], Awaitable[tuple[list[BaseMessage], dict[str, Any]]]
]


@dataclass(frozen=True)
class InputKind:
    """A kind of free-form answer (`waiting_for`) a domain asks `ask_customer` to collect."""

    target: str  # the node that handles the answer
    record: InputRecorder | None = None  # stores it; without one the answer is kept as a message only


@dataclass(frozen=True)
class HandoffKind:
    """A `handoff_reason` a domain raises, and what an agent's resolution of it does."""

    resume: Router  # where the session continues when the agent does not END it
    resolve: HandoffResolver | None = None


@dataclass(frozen=True)
class DomainModule:
    """One domain's part of the graph. Every node has a router; node names are checkpointed, so they are
    stable across releases (see `test_node_names_are_stable`)."""

    name: str
    flow: Callable[[AgentDeps], Flow]  # its methods named after `edges` keys are the nodes
    edges: Mapping[str, Router]  # node name -> the router of its outgoing conditional edge
    retrying: frozenset[str] = field(default_factory=frozenset)  # nodes that call the LLM or an external system
    inputs: Mapping[str, InputKind] = field(default_factory=dict)  # waiting_for -> how to take the answer
    handoffs: Mapping[str, HandoffKind] = field(default_factory=dict)  # handoff_reason -> its resolution

    def nodes(self, deps: AgentDeps) -> dict[str, NodeFn]:
        flow = self.flow(deps)
        return {name: getattr(flow, name) for name in self.edges}


def collect(domains: Sequence[DomainModule], attr: str) -> dict[str, Any]:
    """Merge one registry (`inputs`, `handoffs`, `edges`) across domains; a key may be claimed only once."""
    merged: dict[str, Any] = {}
    for d in domains:
        for key, value in getattr(d, attr).items():
            if key in merged:
                raise ValueError(f"{attr} {key!r} is declared twice (again by {d.name})")
            merged[key] = value
    return merged
