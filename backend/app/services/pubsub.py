"""In-process pub/sub for SSE. One process only; a multi-replica deployment would swap this for
Postgres LISTEN/NOTIFY or Redis without changing the event shapes (CONTRACTS.md §3 SSE)."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Event:
    session_id: str
    type: str
    data: dict[str, Any]


def sse_frame(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


PING_FRAME = ": ping\n\n"


class Broker:
    def __init__(self) -> None:
        self._subs: set[tuple[str | None, asyncio.Queue[Event]]] = set()

    def publish(self, event: Event) -> None:
        for session_filter, queue in list(self._subs):
            if session_filter is None or session_filter == event.session_id:
                # A slow consumer drops events; clients refetch on reconnect.
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait(event)

    def subscribe(self, session_id: str | None) -> tuple[str | None, asyncio.Queue[Event]]:
        sub = (session_id, asyncio.Queue(maxsize=1000))
        self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: tuple[str | None, asyncio.Queue[Event]]) -> None:
        self._subs.discard(sub)

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)

    async def stream(
        self, session_id: str | None, ping_seconds: float, initial: list[str] | None = None
    ) -> AsyncIterator[str]:
        """SSE frames for one session (or all when None), with a `: ping` comment when idle."""
        sub = self.subscribe(session_id)
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
            self.unsubscribe(sub)
