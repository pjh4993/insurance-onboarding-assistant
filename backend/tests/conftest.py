"""Test wiring. DB-backed tests use a throw-away database `onboarding_test` on the compose Postgres
(host port 15432); override with TEST_DATABASE_URL. They are skipped if Postgres is unreachable."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import psycopg
import pytest

from app.config import Settings
from tests.fakes import FakeExternal, FakeLLM

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://onboarding:onboarding@localhost:15432/onboarding_test"
)
FIXED_NOW = datetime(2026, 9, 21, 3, 0, tzinfo=UTC)


def _admin_conninfo(url: str) -> tuple[str, str]:
    plain = url.replace("postgresql+psycopg://", "postgresql://", 1)
    base, _, dbname = plain.rpartition("/")
    dbname = dbname.split("?")[0]
    return f"{base}/postgres", dbname


@pytest.fixture(scope="session")
def database_url() -> str:
    admin, dbname = _admin_conninfo(TEST_DATABASE_URL)
    try:
        with psycopg.connect(admin, autocommit=True, connect_timeout=3) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
            conn.execute(f'CREATE DATABASE "{dbname}"')
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable for DB tests: {exc}")
    return TEST_DATABASE_URL


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        partner_api_url="http://mock.test/partner",
        identity_api_url="http://mock.test/identity",
        contract_api_url="http://mock.test/contract",
        retry_max_attempts=3,
        retry_initial_interval=0.01,
        sse_ping_seconds=0.2,
    )


@pytest.fixture
def external() -> FakeExternal:
    return FakeExternal()


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def clock():
    return lambda: FIXED_NOW


@pytest.fixture
async def runtime(settings, external, llm, clock):
    """A Runtime wired like the app, with fakes for HTTP and the LLM."""
    import httpx

    from app.clients.external import ContractClient, IdentityClient, PartnerClient
    from app.db.engine import init_db, make_engine, make_sessionmaker
    from app.graph.build import build_graph
    from app.graph.checkpointer import open_checkpointer
    from app.graph.deps import Deps
    from app.services.pubsub import Broker
    from app.services.runtime import Runtime

    engine = make_engine(settings.database_url)
    await init_db(engine)
    sm = make_sessionmaker(engine)
    transport = external.transport()
    clients = [
        httpx.AsyncClient(base_url=u, transport=transport)
        for u in (settings.partner_api_url, settings.identity_api_url, settings.contract_api_url)
    ]
    async with open_checkpointer(settings.psycopg_conninfo, settings.aes_key_bytes) as saver:
        broker = Broker()
        holder = {}

        async def on_entity(sid, etype, eid):
            await holder["rt"].publish_entity(sid, etype, eid)

        deps = Deps(
            settings=settings,
            sessionmaker=sm,
            partner=PartnerClient(clients[0]),
            identity=IdentityClient(clients[1]),
            contract=ContractClient(clients[2]),
            llm=llm,
            clock=clock,
            on_entity=on_entity,
        )
        rt = Runtime(graph=build_graph(deps, saver), sessionmaker=sm, broker=broker, settings=settings, clock=clock)
        holder["rt"] = rt
        rt.saver = saver
        yield rt
        await asyncio.gather(*(t for t in rt._tasks.values() if not t.done()), return_exceptions=True)
    for c in clients:
        await c.aclose()
    await engine.dispose()
