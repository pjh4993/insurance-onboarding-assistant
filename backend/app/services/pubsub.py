"""SSE pub/sub. `Broker` is the seam; `InMemoryBroker` serves one process only, and
`PostgresBroker` (pg_broker.py) relays through LISTEN/NOTIFY for several replicas, with the same
event shapes (CONTRACTS.md §3 SSE)."""

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


_CLOSE = Event("", "__close", {})
_Subscription = tuple[str | None, asyncio.Queue[Event]]


class InMemoryBroker:
    def __init__(self, queue_size: int = 1000) -> None:
        self._queue_size = queue_size
        self._subs: set[_Subscription] = set()

    def _matching(self, session_id: str | None) -> list[_Subscription]:
        return [s for s in list(self._subs) if session_id is None or s[0] is None or s[0] == session_id]

    async def publish(self, event: Event) -> None:
        for _, queue in self._matching(event.session_id):
            # A slow consumer drops events; clients refetch on reconnect.
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event)

    def close_streams(self, session_id: str | None = None) -> None:
        """End the streams that see `session_id` (all when None); EventSource reconnects and refetches."""
        for _, queue in self._matching(session_id):
            # Clear room for the sentinel: the dropped events are covered by the refetch.
            while queue.full():
                queue.get_nowait()
            queue.put_nowait(_CLOSE)

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
                if event is _CLOSE:
                    return
                yield sse_frame(event.type, event.data)
        finally:
            self._subs.discard(sub)

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)
