"""Opening and free-form questions: `greet` starts a session, `ask_customer` is the one wait node for every
"please tell me X" pause. Each kind of answer is declared by the domain that asks for it
(`DomainModule.inputs`): the node that handles it, and how to store it."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from onboarding_agent.config import TextSpec
from onboarding_agent.deps import AgentDeps
from onboarding_agent.flows.base import DomainModule, Flow, InputKind, collect
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import human, locale_of, say


class ConversationFlow(Flow):
    def __init__(self, deps: AgentDeps, inputs: Mapping[str, InputKind]) -> None:
        super().__init__(deps)
        self.inputs = inputs

    async def greet(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        text = self.text(lang, "conversation.greeting")
        return {
            "stage": "IDENTITY",
            "waiting_for": "IDENTITY_INFO",
            "last_input": None,
            "identity_result": None,
            "messages": [say(text, self.now())],
        }

    async def ask_customer(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        kind = state.get("waiting_for")
        value = interrupt({"waiting_for": kind})
        actor = state.get("actor") or "CUSTOMER"
        now = self.now()
        out: dict[str, Any] = {"waiting_for": None, "last_input": kind}

        spec = self.inputs.get(kind or "")
        if spec is not None and spec.record is not None:
            text, updates = await spec.record(self, state, value, now)
            out.update(updates)
        else:
            text = str(value.get("text") or "").strip() or "-"
        out["messages"] = [human(text, now, actor=actor, input_type=kind or "")]
        return out


def after_greet(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else "ask_customer"


TEXTS = TextSpec(
    copy={
        "greeting": frozenset(),
    },
)


def module(domains: Sequence[DomainModule]) -> DomainModule:
    """The conversation nodes, taking the kinds of answer `domains` ask for."""
    inputs: dict[str, InputKind] = collect(domains, "inputs")

    def after_ask_customer(state: dict[str, Any]) -> str:
        if has_error(state):
            return HANDOFF
        kind = inputs.get(state.get("last_input") or "")
        return kind.target if kind is not None else HANDOFF

    return DomainModule(
        name="conversation",
        texts=TEXTS,
        flow=lambda deps: ConversationFlow(deps, inputs),
        edges={"greet": after_greet, "ask_customer": after_ask_customer},
    )
