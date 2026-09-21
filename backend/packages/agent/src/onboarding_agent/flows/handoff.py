"""Handing a session to a person: `human_handoff` records why and where to resume, `await_agent` applies
the agent's resolution."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import interrupt

from onboarding_agent.flows.base import DomainModule, Flow
from onboarding_agent.texts import human, locale_of, note, say, t


class HandoffFlow(Flow):
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
                    t(
                        lang,
                        "처리 중 문제가 생겨 상담원을 연결해 드릴게요. 입력하신 내용은 저장돼 있습니다.",
                        "Something went wrong on our side, so I'm connecting you with an agent. "
                        "Everything you've entered is saved.",
                    ),
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
            msgs.append(say(t(lang, "상담원이 상담을 종료했습니다.", "The agent has closed this session."), now))
        elif reason == "IDENTITY_FAILED":
            async with self.d.uow() as uow:
                party = await self._party(uow, state)
                if resolution == "VERIFIED":
                    party.verification_status = "VERIFIED"
                    party.verification_method = "AGENT"
                    party.verified_at = now
                else:
                    party.verification_status = "UNVERIFIED"
                    party.verification_attempts = 0
            await self._touch(state, "party", state["party_id"])
            if resolution == "VERIFIED":
                msgs.append(
                    say(t(lang, "상담원이 본인 확인을 마쳤습니다.", "An agent has verified your identity."), now)
                )
        elif reason in ("NO_ELIGIBLE_PRODUCT", "NEEDS_INCOMPLETE"):
            out.update(stage="PROFILING", needs_complete=False, needs_rounds=0)
        elif reason == "ANSWERS_INCOMPLETE":
            out.update(stage="APPLICATION", answers_complete=False, answers_rounds=0)
        elif reason == "ERROR":
            out["stage"] = state.get("resume_stage") or "IDENTITY"
        out["messages"] = msgs
        return out


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


MODULE = DomainModule(
    name="handoff",
    flow=HandoffFlow,
    edges={
        "human_handoff": after_human_handoff,
        "await_agent": after_await_agent,
    },
    retrying=frozenset(),
)
