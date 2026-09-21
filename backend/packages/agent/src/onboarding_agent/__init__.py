"""LangGraph onboarding agent. It reaches the domain DB and external systems only through the
`onboarding_core.ports` protocols, so it never imports SQLAlchemy or FastAPI.

Wiring: build `AgentDeps`, compile with `build_graph(deps, checkpointer)`, drive with `AgentRunner`."""

from onboarding_agent.build import build_graph
from onboarding_agent.checkpointer import open_checkpointer
from onboarding_agent.deps import AgentConfig, AgentDeps
from onboarding_agent.llm.provider import BedrockStructuredLLM, StructuredLLM
from onboarding_agent.runner import AgentRunner, AgentSnapshot, MessageSink, chat_message

__all__ = [
    "AgentConfig",
    "AgentDeps",
    "AgentRunner",
    "AgentSnapshot",
    "BedrockStructuredLLM",
    "MessageSink",
    "StructuredLLM",
    "build_graph",
    "chat_message",
    "open_checkpointer",
]
