"""The graph by domain. Each stage module owns its nodes, their routers, which of them retry, the kinds of
answer it asks for and the handoff reasons it raises; `conversation` and `handoff` are built from those
declarations. `build.py` assembles everything into one flat graph, in this order."""

from __future__ import annotations

from onboarding_agent.flows import application, conversation, handoff, identity, profiling, recommendation
from onboarding_agent.flows.base import DomainModule, collect

STAGES: tuple[DomainModule, ...] = (identity.MODULE, profiling.MODULE, recommendation.MODULE, application.MODULE)

DOMAINS: tuple[DomainModule, ...] = (conversation.module(STAGES), *STAGES, handoff.module(STAGES))

collect(DOMAINS, "edges")  # a node belongs to exactly one domain

__all__ = ["DOMAINS", "STAGES", "DomainModule"]
