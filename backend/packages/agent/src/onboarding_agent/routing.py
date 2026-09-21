"""Routing helpers shared by the domain flows. Routers (`after_<node>`) live next to their node in
`onboarding_agent.flows`; they read only the state — never the DB — so a branch can be replayed from the
checkpoint alone and tested without a database (wiki/state-model.md §3)."""

from __future__ import annotations

from typing import Any

HANDOFF = "human_handoff"


def has_error(state: dict[str, Any]) -> bool:
    return bool(state.get("last_error"))
