"""Everything a node needs from the outside world, injected when the graph is built."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.external import ContractClient, IdentityClient, PartnerClient
from app.config import Settings
from app.llm.provider import StructuredLLM
from app.util import Clock, utcnow

EntityListener = Callable[[str, str, str], Awaitable[None]]  # (session_id, entity_type, entity_id)


async def _ignore(session_id: str, entity_type: str, entity_id: str) -> None:
    return None


@dataclass
class Deps:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    partner: PartnerClient
    identity: IdentityClient
    contract: ContractClient
    llm: StructuredLLM
    clock: Clock = utcnow
    on_entity: EntityListener = field(default=_ignore)
