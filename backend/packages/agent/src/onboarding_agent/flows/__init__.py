"""The graph by domain. Each module owns its nodes, their routers and which of them retry; `build.py`
assembles them into one flat graph, in this order."""

from __future__ import annotations

from onboarding_agent.flows import application, conversation, handoff, identity, profiling, recommendation
from onboarding_agent.flows.base import DomainModule

DOMAINS: tuple[DomainModule, ...] = (
    conversation.MODULE,
    identity.MODULE,
    profiling.MODULE,
    recommendation.MODULE,
    application.MODULE,
    handoff.MODULE,
)

__all__ = ["DOMAINS", "DomainModule"]
