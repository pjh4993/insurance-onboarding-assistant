"""Opening and free-form questions: `greet` starts a session, `ask_customer` is the one wait node for every
"please tell me X" pause. Each kind of answer is declared by the domain that asks for it
(`DomainModule.inputs`): the node that handles it, and how to store it."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from onboarding_agent.deps import AgentDeps
from onboarding_agent.flows.base import DomainModule, Flow, InputKind, collect
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import human, locale_of, say, t


class ConversationFlow(Flow):
    def __init__(self, deps: AgentDeps, inputs: Mapping[str, InputKind]) -> None:
        super().__init__(deps)
        self.inputs = inputs

    async def greet(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        text = t(
            lang,
            "안녕하세요! 보험 가입을 도와드릴게요. 먼저 본인 확인을 위해 이름, 이메일, 휴대폰 번호, "
            "신분증 종류와 번호를 알려 주세요. 파트너사 구매 기록 조회(제3자 제공)에 동의하시면 "
            "확인이 더 빨라집니다.",
            "Hi! I'll help you find the right cover. First, to verify your identity, please share your "
            "full name, email, phone number and an ID document. If you consent to us checking your "
            "purchase history with our partner, verification is faster.",
        )
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
        flow=lambda deps: ConversationFlow(deps, inputs),
        edges={"greet": after_greet, "ask_customer": after_ask_customer},
    )
