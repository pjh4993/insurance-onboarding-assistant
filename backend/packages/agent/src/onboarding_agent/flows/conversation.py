"""Opening and free-form questions: `greet` starts a session and asks what brings the customer here,
`understand_intake` answers that first message and notes which product it points to, and `ask_customer` is
the one wait node for every "please tell me X" pause. Each kind of answer is declared by the domain that asks
for it (`DomainModule.inputs`): the node that handles it, how to store it, and the form its prompt shows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from onboarding_agent.config import TextSpec
from onboarding_agent.deps import AgentDeps
from onboarding_agent.flows.base import DomainModule, Flow, InputKind, collect
from onboarding_agent.llm.schemas import IntakeReply
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import human, locale_of, say


async def record_intake(
    flow: Flow, state: dict[str, Any], value: dict[str, Any], now: datetime
) -> tuple[str, dict[str, Any]]:
    """The first thing the customer typed or picked ("" when they just pressed start). It stays in the state
    for the needs extraction, in a dict so the checkpoint encrypts it."""
    text = str(value.get("text") or "").strip()
    return text, {"intake": {"text": text}, "product_interest": None}


class ConversationFlow(Flow):
    def __init__(self, deps: AgentDeps, inputs: Mapping[str, InputKind]) -> None:
        super().__init__(deps)
        self.inputs = inputs

    async def greet(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        text = self.text(lang, "conversation.greeting")
        return {
            "stage": "IDENTITY",
            "waiting_for": "INTAKE",
            "last_input": None,
            "identity_result": None,
            "messages": [say(text, self.now())],
        }

    async def understand_intake(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        """Replies to the first message (answers an insurance question briefly, or says what this assistant
        is for), infers the product it points to, and says what comes next: identity, then a few questions."""
        lang, now = locale_of(state), self.now()
        text = str((state.get("intake") or {}).get("text") or "").strip()
        interest = None
        if not text:
            reply = self.text(lang, "conversation.intake_opener")
        else:
            async with self.d.uow() as uow:
                party = await self._party(uow, state)
                products = await uow.catalog.active_products(state["market"])
            catalog = "\n".join(f"- {p.product_type}: {p.marketing_name}" for p in products)
            instructions = self.prompt("understand_intake", "instructions", products=catalog)
            out = await self.d.llm.extract(
                "understand_intake", IntakeReply, [self._system(state, party, instructions), HumanMessage(text)]
            )
            reply = out.reply.strip() or self.text(lang, "conversation.intake_thanks")
            interest = out.product_interest
        message = f"{reply} {self.text(lang, 'conversation.intake_next')}"
        return {"product_interest": interest, "last_input": None, "messages": [say(message, now)]}

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
        out["form_topic"] = None
        if text:  # an empty intake (the customer just pressed start) leaves no message
            out["messages"] = [human(text, now, actor=actor, input_type=kind or "")]
        return out


def after_greet(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else "ask_customer"


def after_understand_intake(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else "collect_identity"


TEXTS = TextSpec(
    copy={
        "greeting": frozenset(),
        "intake_opener": frozenset(),
        "intake_thanks": frozenset(),
        "intake_next": frozenset(),
    },
    llm={
        "understand_intake": {
            "instructions": frozenset({"products"}),
        },
    },
)

INPUTS = {"INTAKE": InputKind("understand_intake", record_intake)}


def module(domains: Sequence[DomainModule]) -> DomainModule:
    """The conversation nodes, taking the kinds of answer `domains` ask for."""
    inputs: dict[str, InputKind] = {**INPUTS, **collect(domains, "inputs")}

    def after_ask_customer(state: dict[str, Any]) -> str:
        if has_error(state):
            return HANDOFF
        kind = inputs.get(state.get("last_input") or "")
        return kind.target if kind is not None else HANDOFF

    return DomainModule(
        name="conversation",
        texts=TEXTS,
        flow=lambda deps: ConversationFlow(deps, inputs),
        edges={"greet": after_greet, "understand_intake": after_understand_intake, "ask_customer": after_ask_customer},
        retrying=frozenset({"understand_intake"}),
        inputs=INPUTS,
    )
