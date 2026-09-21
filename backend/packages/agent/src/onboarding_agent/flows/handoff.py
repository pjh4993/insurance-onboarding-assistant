"""Handing a session to a person: `human_handoff` records why and where to resume, `await_agent` applies
the agent's resolution. What a resolution does, and where the session goes next, is declared by the domain
that raised the reason (`DomainModule.handoffs`)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import interrupt

from onboarding_agent.config import TextSpec
from onboarding_agent.deps import AgentDeps
from onboarding_agent.flows.base import DomainModule, Flow, HandoffKind, collect
from onboarding_agent.texts import human, locale_of, note, say


async def resolve_error(
    flow: Flow, state: dict[str, Any], resolution: str | None, now: datetime
) -> tuple[list[BaseMessage], dict[str, Any]]:
    return [], {"stage": state.get("resume_stage") or "IDENTITY"}


def resume_error(state: dict[str, Any]) -> str:
    """An ERROR handoff re-runs the node that failed, with the input it had."""
    return state.get("resume_node") or END


class HandoffFlow(Flow):
    def __init__(self, deps: AgentDeps, handoffs: Mapping[str, HandoffKind]) -> None:
        super().__init__(deps)
        self.handoffs = handoffs

    async def human_handoff(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        err = state.get("last_error")
        reason = "ERROR" if err else state.get("handoff_reason") or "ERROR"
        out: dict[str, Any] = {
            "stage": "HANDOFF",
            "waiting_for": "AGENT",
            "handoff_reason": reason,
            "handoff_resolution": None,
            "resume_stage": state.get("stage") if state.get("stage") != "HANDOFF" else state.get("resume_stage"),
            "resume_node": err["node"] if err else None,
        }
        if err:
            lang = locale_of(state)
            out["messages"] = [
                note(f"Handoff: {err['node']} failed after {err['attempts']} attempts ({err['kind']}).", self.now()),
                say(
                    self.text(lang, "handoff.error_handoff"),
                    self.now(),
                ),
            ]
        return out

    async def await_agent(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        value = interrupt({"waiting_for": "AGENT", "reason": state.get("handoff_reason")})
        lang, now = locale_of(state), self.now()
        resolution = value.get("resolution")
        reason = state.get("handoff_reason")
        agent_note = str(value.get("note") or "").strip()
        msgs: list[BaseMessage] = [
            human(agent_note or f"Agent resolution: {resolution}", now, actor="AGENT", input_type="AGENT")
        ]
        out: dict[str, Any] = {
            "handoff_resolution": resolution,
            "waiting_for": None,
            "last_error": None,
        }
        if reason != "ERROR":
            # An ERROR handoff re-runs the failed node with the input it had; others start fresh.
            out["last_input"] = None
        if resolution == "END":
            out["stage"] = "WITHDRAWN"
            msgs.append(say(self.text(lang, "handoff.closed_by_agent"), now))
        elif (kind := self.handoffs.get(reason or "")) is not None and kind.resolve is not None:
            extra, updates = await kind.resolve(self, state, resolution, now)
            msgs += extra
            out.update(updates)
        out["messages"] = msgs
        return out


def after_human_handoff(state: dict[str, Any]) -> str:
    return "await_agent"


TEXTS = TextSpec(
    copy={
        "error_handoff": frozenset(),
        "closed_by_agent": frozenset(),
    },
)


def module(domains: Sequence[DomainModule]) -> DomainModule:
    """The handoff nodes, resolving the reasons `domains` raise plus ERROR (a node that ran out of retries)."""
    handoffs: dict[str, HandoffKind] = {
        "ERROR": HandoffKind(resume_error, resolve_error),
        **collect(domains, "handoffs"),
    }

    def after_await_agent(state: dict[str, Any]) -> str:
        """Where an agent's resolution sends the session."""
        if state.get("handoff_resolution") == "END":
            return END
        kind = handoffs.get(state.get("handoff_reason") or "")
        return kind.resume(state) if kind is not None else END

    return DomainModule(
        name="handoff",
        texts=TEXTS,
        flow=lambda deps: HandoffFlow(deps, handoffs),
        edges={"human_handoff": after_human_handoff, "await_agent": after_await_agent},
    )
