"""FastAPI application factory and composition root: `create_app()` plugs the backend's adapters (DB unit
of work, HTTP clients, SSE broker) into the agent's ports. Tests pass fakes through `Overrides`."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI

from app.api.routes import router
from app.clients.external import ContractClient, IdentityClient, PartnerClient, make_http
from app.config import Settings, get_settings
from app.db.engine import init_db, make_engine, make_sessionmaker
from app.db.uow import uow_factory
from app.services.pg_broker import PostgresBroker
from app.services.pubsub import Broker, InMemoryBroker
from app.services.runtime import Runtime, entity_listener
from app.telemetry import setup_logging, setup_otel
from onboarding_agent import (
    AgentConfig,
    AgentDeps,
    AgentRunner,
    BedrockStructuredLLM,
    StructuredLLM,
    build_graph,
    open_checkpointer,
)
from onboarding_agent.config import Bundle, load_bundle
from onboarding_core.util import Clock, utcnow


@dataclass
class Overrides:
    """Test seams: HTTP transport for the partner/identity/contract systems, the LLM, the clock and the
    agent config bundle."""

    transport: httpx.AsyncBaseTransport | None = None
    llm: StructuredLLM | None = None
    clock: Clock | None = None
    bundle: Bundle | None = None


log = logging.getLogger(__name__)


def agent_config(settings: Settings) -> AgentConfig:
    return AgentConfig(
        aes_key=settings.aes_key_bytes,
        hmac_key=settings.session_hmac_key,
        retry_max_attempts=settings.retry_max_attempts,
        retry_initial_interval=settings.retry_initial_interval,
    )


def bedrock_llm(settings: Settings, bundle: Bundle) -> BedrockStructuredLLM:
    return BedrockStructuredLLM(bundle=bundle, region=settings.aws_region, endpoint_url=settings.bedrock_endpoint_url)


async def agent_bundle(settings: Settings) -> Bundle:
    """Read and validate the config bundle once, at startup: a bad one stops the service here."""
    bundle = await asyncio.to_thread(
        load_bundle,
        settings.agent_config_uri,
        settings.agent_config_version,
        allowed_model_ids=settings.allowed_model_ids,
    )
    log.info(
        "agent config loaded",
        extra={"agent_config.version": bundle.version, "agent_config.source": bundle.source},
    )
    return bundle


def create_app(settings: Settings | None = None, overrides: Overrides | None = None) -> FastAPI:
    settings = settings or get_settings()
    overrides = overrides or Overrides()
    setup_logging(settings)

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
            broker: Broker = InMemoryBroker()
            if settings.sse_broker == "postgres":
                broker = await stack.enter_async_context(PostgresBroker(settings.psycopg_conninfo))
            clock = overrides.clock or utcnow
            bundle = overrides.bundle or await agent_bundle(settings)
            deps = AgentDeps(
                config=agent_config(settings),
                uow=uow_factory(sessionmaker),
                partner=PartnerClient(partner),
                identity=IdentityClient(identity),
                contract=ContractClient(contract),
                llm=overrides.llm or bedrock_llm(settings, bundle),
                bundle=bundle,
                clock=clock,
                on_entity=entity_listener(broker),
            )
            agent = AgentRunner(build_graph(deps, checkpointer), retry_max_attempts=settings.retry_max_attempts)
            rt = Runtime(
                agent=agent,
                sessionmaker=sessionmaker,
                broker=broker,
                settings=settings,
                languages=bundle.languages,
                default_language=bundle.default_language,
                clock=clock,
            )
            app.state.settings = settings
            app.state.broker = broker
            app.state.runtime = rt
            app.state.engine = engine
            yield

    app = FastAPI(title="Onboarding Assistant API", version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    setup_otel(app, settings)
    return app


app = create_app()
