"""SSE pub/sub. `Broker` is the seam; `InMemoryBroker` serves one process only, and a multi-replica
deployment swaps in a Postgres LISTEN/NOTIFY or Redis implementation without changing the event
shapes (CONTRACTS.md §3 SSE)."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Event:
    session_id: str
    type: str
    data: dict[str, Any]


def sse_frame(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


PING_FRAME = ": ping\n\n"


class Broker(Protocol):
    async def publish(self, event: Event) -> None:
        """Deliver `event` to every stream subscribed to its session, or to all sessions."""
        ...

    def stream(
        self, session_id: str | None, ping_seconds: float, initial: list[str] | None = None
    ) -> AsyncIterator[str]:
        """SSE frames for one session (or all when None), with a `: ping` comment when idle."""
        ...


_Subscription = tuple[str | None, asyncio.Queue[Event]]


class InMemoryBroker:
    def __init__(self, queue_size: int = 1000) -> None:
        self._queue_size = queue_size
        self._subs: set[_Subscription] = set()

    async def publish(self, event: Event) -> None:
        for session_filter, queue in list(self._subs):
            if session_filter is None or session_filter == event.session_id:
                # A slow consumer drops events; clients refetch on reconnect.
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait(event)

    async def stream(
        self, session_id: str | None, ping_seconds: float, initial: list[str] | None = None
    ) -> AsyncIterator[str]:
        sub: _Subscription = (session_id, asyncio.Queue(maxsize=self._queue_size))
        self._subs.add(sub)
        try:
            for frame in initial or []:
                yield frame
            while True:
                try:
                    event = await asyncio.wait_for(sub[1].get(), timeout=ping_seconds)
                except TimeoutError:
                    yield PING_FRAME
                    continue
                yield sse_frame(event.type, event.data)
        finally:
            self._subs.discard(sub)

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)
