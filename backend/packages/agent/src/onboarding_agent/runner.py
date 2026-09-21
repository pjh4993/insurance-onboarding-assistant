"""The agent's public entry point: start a conversation, resume it with customer or agent input, and
read where it stands. A run whose node exhausted its retries (or hit a bug) is routed to
`human_handoff` instead of failing, so the conversation always ends a turn in a waiting state.

Callers get chat messages as plain dicts (`chat_message`) and never touch LangGraph types."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from onboarding_agent.deps import AgentDeps
from onboarding_agent.flows import FORMS
from onboarding_agent.flows.base import Flow
from onboarding_agent.state import initial_state

log = logging.getLogger(__name__)

MessageSink = Callable[[dict[str, Any]], Awaitable[None]]


def chat_message(m: BaseMessage) -> dict[str, Any]:
    """A conversation message as the API shows it: id, role, text and created_at."""
    if isinstance(m, AIMessage):
        role = "assistant"
    elif isinstance(m, HumanMessage):
        role = m.additional_kwargs.get("role", "customer")
    else:
        role = "system"
    return {
        "id": m.id,
        "role": role,
        "text": m.content if isinstance(m.content, str) else str(m.content),
        "created_at": m.additional_kwargs.get("created_at"),
    }


@dataclass(frozen=True)
class AgentSnapshot:
    values: dict[str, Any]  # graph state (stage, entity ids, routing signals), without messages
    messages: list[dict[str, Any]]  # the conversation, as `chat_message` dicts
    waiting_for: str | None  # the input the pending interrupt asks for
    next_node: str | None


class AgentRunner:
    def __init__(self, graph: CompiledStateGraph, *, retry_max_attempts: int, deps: AgentDeps | None = None) -> None:
        self.graph = graph
        self.retry_max_attempts = retry_max_attempts
        self.deps = deps  # needed to build prompt forms; without it `form` returns None

    async def form(self, values: dict[str, Any], waiting_for: str | None, locale: str) -> dict[str, Any] | None:
        """The small form (`FormSpec`, CONTRACTS.md §3) the pending wait shows, or None. It is built from the
        state and the domain DB when read, so labels follow the session's current language and the checkpoint
        holds no pre-filled PII."""
        build = FORMS.get(waiting_for or "")
        if build is None or self.deps is None:
            return None
        return await build(Flow(self.deps), values, locale)

    @staticmethod
    def config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    async def start(
        self,
        thread_id: str,
        *,
        session_id: str,
        party_id: str,
        market: str,
        locale: str,
        on_message: MessageSink,
        log_extra: Mapping[str, Any] | None = None,
    ) -> None:
        state = initial_state(session_id=session_id, party_id=party_id, market=market, locale=locale)
        await self._run(thread_id, state, on_message, log_extra)

    async def resume(
        self,
        thread_id: str,
        data: dict[str, Any],
        *,
        actor: str,
        mode: str,
        locale: str,
        on_message: MessageSink,
        log_extra: Mapping[str, Any] | None = None,
    ) -> None:
        # The session's current language rides on every resume, so a change applies from the next step on.
        command = Command(resume=data, update={"actor": actor, "mode": mode, "locale": locale})
        await self._run(thread_id, command, on_message, log_extra)

    async def snapshot(self, thread_id: str) -> AgentSnapshot:
        snap = await self.graph.aget_state(self.config(thread_id))
        values = dict(snap.values or {})
        messages = [chat_message(m) for m in values.pop("messages", None) or []]
        waiting = None
        for task in snap.tasks:
            for intr in task.interrupts:
                if isinstance(intr.value, dict) and intr.value.get("waiting_for"):
                    waiting = intr.value["waiting_for"]
        return AgentSnapshot(
            values=values,
            messages=messages,
            waiting_for=waiting,
            next_node=snap.next[0] if snap.next else None,
        )

    # ------------------------------------------------------------------------------- running

    async def _run(
        self, thread_id: str, graph_input: Any, on_message: MessageSink, log_extra: Mapping[str, Any] | None
    ) -> None:
        config = self.config(thread_id)
        extra = dict(log_extra or {})
        try:
            await self._stream(graph_input, config, on_message)
        except Exception as exc:  # retries are exhausted (or a bug): hand the session to an agent
            log.warning("graph run failed", extra={**extra, "error.type": type(exc).__name__})
            try:
                await self._recover(config, exc, on_message)
            except Exception:
                log.exception("could not route the failure to human_handoff", extra=extra)

    async def _stream(self, graph_input: Any, config: dict[str, Any], on_message: MessageSink) -> None:
        async for chunk in self.graph.astream(graph_input, config, stream_mode="updates"):
            for node, update in chunk.items():
                if node.startswith("__") or not isinstance(update, dict):
                    continue
                for message in update.get("messages") or []:
                    await on_message(chat_message(message))

    async def _recover(self, config: dict[str, Any], exc: Exception, on_message: MessageSink) -> None:
        snapshot = await self.graph.aget_state(config)
        failed = snapshot.next[0] if snapshot.next else "unknown"
        error = {"node": failed, "kind": type(exc).__name__, "attempts": self.retry_max_attempts}
        if failed == "unknown":
            return
        await self.graph.aupdate_state(config, {"last_error": error}, as_node=failed)
        await self._stream(None, config, on_message)
