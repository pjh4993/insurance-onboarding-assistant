"""Everything a node needs from the outside world, injected when the graph is built. The agent sees
the domain DB and the external systems only through the `onboarding_core.ports` protocols."""

from __future__ import annotations

from dataclasses import dataclass, field

from onboarding_agent.config import Bundle, default_bundle
from onboarding_agent.llm.provider import StructuredLLM
from onboarding_core.ports import (
    ContractGateway,
    EntityListener,
    IdentityGateway,
    PartnerGateway,
    UnitOfWorkFactory,
)
from onboarding_core.util import Clock, utcnow


async def _ignore(session_id: str, entity_type: str, entity_id: str) -> None:
    return None


@dataclass(frozen=True)
class AgentConfig:
    aes_key: bytes  # encrypts the ID document number at rest
    hmac_key: str  # fingerprints the ID document number for lookups
    retry_max_attempts: int = 3
    retry_initial_interval: float = 0.5


@dataclass
class AgentDeps:
    config: AgentConfig
    uow: UnitOfWorkFactory
    partner: PartnerGateway
    identity: IdentityGateway
    contract: ContractGateway
    llm: StructuredLLM
    clock: Clock = utcnow
    on_entity: EntityListener = field(default=_ignore)
    bundle: Bundle = field(default_factory=default_bundle)  # models, prompts and copy
