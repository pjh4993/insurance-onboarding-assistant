"""FastAPI application factory. `create_app()` wires real clients; tests pass fakes."""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI

from app.api.routes import router
from app.clients.external import ContractClient, IdentityClient, PartnerClient, make_http
from app.config import Settings, get_settings
from app.db.engine import init_db, make_engine, make_sessionmaker
from app.graph.build import build_graph
from app.graph.checkpointer import open_checkpointer
from app.graph.deps import Deps
from app.llm.provider import BedrockStructuredLLM, StructuredLLM
from app.services.pubsub import InMemoryBroker
from app.services.runtime import Runtime
from app.util import Clock, utcnow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@dataclass
class Overrides:
    """Test seams: HTTP transport for the partner/identity/contract systems, the LLM and the clock."""

    transport: httpx.AsyncBaseTransport | None = None
    llm: StructuredLLM | None = None
    clock: Clock | None = None


def create_app(settings: Settings | None = None, overrides: Overrides | None = None) -> FastAPI:
    settings = settings or get_settings()
    overrides = overrides or Overrides()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with AsyncExitStack() as stack:
            engine = make_engine(settings.database_url)
            stack.push_async_callback(engine.dispose)
            await init_db(engine)
            sessionmaker = make_sessionmaker(engine)

            def http(base_url: str) -> httpx.AsyncClient:
                if overrides.transport is not None:
                    return httpx.AsyncClient(base_url=base_url.rstrip("/"), transport=overrides.transport)
                return make_http(base_url, settings.http_timeout_seconds)

            partner = await stack.enter_async_context(http(settings.partner_api_url))
            identity = await stack.enter_async_context(http(settings.identity_api_url))
            contract = await stack.enter_async_context(http(settings.contract_api_url))
            checkpointer = await stack.enter_async_context(
                open_checkpointer(settings.psycopg_conninfo, settings.aes_key_bytes)
            )
            broker = InMemoryBroker()
            clock = overrides.clock or utcnow
            holder: dict[str, Any] = {}

            async def on_entity(session_id: str, entity_type: str, entity_id: str) -> None:
                await holder["runtime"].publish_entity(session_id, entity_type, entity_id)

            deps = Deps(
                settings=settings,
                sessionmaker=sessionmaker,
                partner=PartnerClient(partner),
                identity=IdentityClient(identity),
                contract=ContractClient(contract),
                llm=overrides.llm or BedrockStructuredLLM(settings),
                clock=clock,
                on_entity=on_entity,
            )
            graph = build_graph(deps, checkpointer)
            rt = Runtime(graph=graph, sessionmaker=sessionmaker, broker=broker, settings=settings, clock=clock)
            holder["runtime"] = rt
            app.state.settings = settings
            app.state.broker = broker
            app.state.runtime = rt
            app.state.engine = engine
            yield

    app = FastAPI(title="Onboarding Assistant API", version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
