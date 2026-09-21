import asyncio
import uuid

import psycopg
import pytest

from app.services.pg_broker import MAX_PAYLOAD_BYTES, PostgresBroker
from app.services.pubsub import Event, InMemoryBroker


async def _subscribed(agen) -> asyncio.Future:
    """Start waiting on the stream; the subscription exists once the generator has run once."""
    nxt = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0.05)
    return nxt


async def test_close_streams_ends_matching_streams_only():
    broker = InMemoryBroker()
    s1, s2, every = (broker.stream(sid, ping_seconds=5) for sid in ("s1", "s2", None))
    n1, n2, nall = [await _subscribed(g) for g in (s1, s2, every)]
    broker.close_streams("s1")
    for fut in (n1, nall):
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(fut, 1)
    assert not n2.done()
    await broker.publish(Event("s2", "prompt.updated", {"x": 1}))
    assert (await asyncio.wait_for(n2, 1)).startswith("event: prompt.updated")
    await s2.aclose()
    assert broker.subscriber_count == 0


@pytest.fixture
def conninfo(settings) -> str:
    return settings.psycopg_conninfo


@pytest.fixture
def channel() -> str:
    return f"test_{uuid.uuid4().hex[:12]}"


async def test_event_published_on_one_replica_reaches_another(conninfo, channel):
    async with PostgresBroker(conninfo, channel) as a, PostgresBroker(conninfo, channel) as b:
        await asyncio.wait_for(asyncio.gather(a.listening.wait(), b.listening.wait()), 5)
        stream = b.stream("s1", ping_seconds=5)
        nxt = await _subscribed(stream)
        await a.publish(Event("other", "message.appended", {"session_id": "other"}))
        await a.publish(Event("s1", "message.appended", {"session_id": "s1", "text": "안녕하세요"}))
        frame = await asyncio.wait_for(nxt, 5)
        assert frame == 'event: message.appended\ndata: {"session_id": "s1", "text": "안녕하세요"}\n\n'
        await stream.aclose()


async def test_oversized_event_closes_the_session_streams(conninfo, channel):
    async with PostgresBroker(conninfo, channel) as broker:
        await asyncio.wait_for(broker.listening.wait(), 5)
        target, bystander = broker.stream("s1", ping_seconds=5), broker.stream("s2", ping_seconds=5)
        n1, n2 = await _subscribed(target), await _subscribed(bystander)
        await broker.publish(Event("s1", "message.appended", {"text": "x" * MAX_PAYLOAD_BYTES}))
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(n1, 5)
        assert not n2.done()
        n2.cancel()
        await asyncio.gather(n2, return_exceptions=True)
        assert broker._local.subscriber_count == 0


async def test_lost_listen_connection_reconnects_and_closes_streams(conninfo, channel):
    async with PostgresBroker(conninfo, channel, retry_seconds=0.05) as broker:
        await asyncio.wait_for(broker.listening.wait(), 5)
        stream = broker.stream("s1", ping_seconds=5)
        nxt = await _subscribed(stream)
        async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as admin:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE query = %s",
                (f'LISTEN "{channel}"',),
            )
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(nxt, 5)
        await asyncio.wait_for(broker.listening.wait(), 5)
        again = broker.stream("s1", ping_seconds=5)
        nxt = await _subscribed(again)
        await broker.publish(Event("s1", "prompt.updated", {"session_id": "s1"}))
        assert (await asyncio.wait_for(nxt, 5)).startswith("event: prompt.updated")
        await again.aclose()
