"""Deterministic ids for the entities a node creates."""

from __future__ import annotations

import uuid

# Namespace for node-scoped ids: uuid5(NS, f"{thread_id}:{node}:{step}:{extra}")
NODE_ID_NAMESPACE = uuid.UUID("6d1f7c43-6a5e-4c55-9d7c-0c3b1c1e0b7a")


def node_uuid(thread_id: str, node: str, step: int | str, extra: str = "") -> uuid.UUID:
    """Id for an entity a node creates. Re-running the same node at the same step yields the
    same id, so the write becomes an upsert (state-model.md §5)."""
    return uuid.uuid5(NODE_ID_NAMESPACE, f"{thread_id}:{node}:{step}:{extra}")
