"""Cross-replica SSE broker over Postgres LISTEN/NOTIFY.

Every replica publishes with NOTIFY and keeps one LISTEN connection that feeds its local
InMemoryBroker, so each event reaches the streams held by every replica. Delivery is at most once:
whenever an event may have been missed, the affected streams are closed and the browser's
reconnect refetches the snapshot.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import psycopg
from psycopg import sql
from psycopg_pool import AsyncConnectionPool

from app.services.pubsub import Event, InMemoryBroker

log = logging.getLogger(__name__)

CHANNEL = "onboarding_events"
# NOTIFY rejects payloads of 8000 bytes or more.
MAX_PAYLOAD_BYTES = 7900
RESYNC = "__resync"


def encode(event: Event) -> str:
    payload = json.dumps({"s": event.session_id, "t": event.type, "d": event.data}, ensure_ascii=False, default=str)
    if len(payload.encode()) > MAX_PAYLOAD_BYTES:
        return json.dumps({"s": event.session_id, "t": RESYNC})
    return payload


class PostgresBroker:
    def __init__(
        self,
        conninfo: str,
        channel: str = CHANNEL,
        health_check_seconds: float = 30.0,
        retry_seconds: float = 1.0,
    ) -> None:
        self._conninfo = conninfo
        self._channel = channel
        self._health_check_seconds = health_check_seconds
        self._retry_seconds = retry_seconds
        self._local = InMemoryBroker()
        self._pool = AsyncConnectionPool(conninfo, min_size=1, max_size=2, kwargs={"autocommit": True}, open=False)
        self._listener: asyncio.Task[None] | None = None
        self.listening = asyncio.Event()

    async def start(self) -> None:
        await self._pool.open()
        self._listener = asyncio.create_task(self._listen(), name="pg-broker-listen")

    async def aclose(self) -> None:
        if self._listener:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
        self._local.close_streams()
        await self._pool.close()

    async def __aenter__(self) -> PostgresBroker:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def publish(self, event: Event) -> None:
        try:
            async with self._pool.connection() as conn:
                await conn.execute("SELECT pg_notify(%s, %s)", (self._channel, encode(event)))
        except psycopg.Error:
            # Same contract as a dropped in-memory event: the reconnect refetch covers it.
            log.warning("could not publish %s for session %s", event.type, event.session_id, exc_info=True)

    def stream(
        self, session_id: str | None, ping_seconds: float, initial: list[str] | None = None
    ) -> AsyncIterator[str]:
        return self._local.stream(session_id, ping_seconds, initial)

    async def _listen(self) -> None:
        connected_before = False
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(self._conninfo, autocommit=True) as conn:
                    await conn.execute(sql.SQL("LISTEN {}").format(sql.Identifier(self._channel)))
                    if connected_before:
                        # Events published while we were not listening are gone.
                        self._local.close_streams()
                    connected_before = True
                    self.listening.set()
                    while True:
                        async for notify in conn.notifies(timeout=self._health_check_seconds):
                            await self._dispatch(notify.payload)
                        # A half-open TCP connection yields nothing; a round trip proves it is alive.
                        await conn.execute("SELECT 1")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.listening.clear()
                log.warning("LISTEN connection lost; reconnecting", exc_info=True)
                await asyncio.sleep(self._retry_seconds)

    async def _dispatch(self, payload: str) -> None:
        try:
            msg: dict[str, Any] = json.loads(payload)
            session_id, event_type = msg["s"], msg["t"]
        except (ValueError, KeyError, TypeError):
            log.warning("ignoring malformed notification")
            return
        if event_type == RESYNC:
            self._local.close_streams(session_id)
        else:
            await self._local.publish(Event(session_id, event_type, msg.get("d") or {}))
