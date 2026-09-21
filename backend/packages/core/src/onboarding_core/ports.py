"""Ports: what the domain needs from persistence and from external systems. Adapters live in the
backend (`app/db/uow.py`, `app/clients/external.py`); tests may substitute in-memory ones.

Unit-of-work semantics: entities returned by a repository are tracked, so a change made to one inside
`async with uow_factory() as uow:` is persisted when the block exits without an exception, and rolled
back otherwise. `add` starts tracking a new entity; `save` upserts by primary key and returns the
tracked instance (a re-run of a node writes the same ids, so its writes are idempotent)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Iterable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any, Protocol

from onboarding_core.application.models import Application
from onboarding_core.catalog.models import EligibilityRule, Product, TargetMarket
from onboarding_core.needs.models import InsurableObject, NeedsAssessment
from onboarding_core.party.models import Party
from onboarding_core.quoting.models import Quote
from onboarding_core.recommendation.models import Recommendation

# ------------------------------------------------------------------------------------ persistence


class PartyRepository(Protocol):
    async def get(self, party_id: uuid.UUID) -> Party | None: ...
    async def add(self, party: Party) -> None: ...
    async def save(self, party: Party) -> Party: ...


class CatalogRepository(Protocol):
    async def product(self, product_code: str) -> Product | None: ...
    async def active_products(self, market: str) -> list[Product]:
        """ACTIVE products sold in `market`, ordered by product code."""
        ...

    async def rules(self) -> list[EligibilityRule]: ...
    async def target_markets(self) -> list[TargetMarket]: ...


class NeedsRepository(Protocol):
    async def get(self, needs_assessment_id: uuid.UUID) -> NeedsAssessment | None: ...
    async def add(self, needs: NeedsAssessment) -> None: ...
    async def latest_version(self, party_id: uuid.UUID) -> int:
        """The party's highest assessment version, 0 when it has none."""
        ...


class InsurableObjectRepository(Protocol):
    async def get(self, insurable_object_id: uuid.UUID) -> InsurableObject | None: ...
    async def list(self, ids: Iterable[uuid.UUID]) -> list[InsurableObject]: ...
    async def save(self, obj: InsurableObject) -> InsurableObject: ...


class RecommendationRepository(Protocol):
    async def get(self, recommendation_id: uuid.UUID) -> Recommendation | None: ...
    async def list(self, ids: Iterable[uuid.UUID]) -> list[Recommendation]: ...
    async def save(self, rec: Recommendation) -> Recommendation: ...


class QuoteRepository(Protocol):
    async def get(self, quote_id: uuid.UUID) -> Quote | None: ...
    async def save(self, quote: Quote) -> Quote: ...


class ApplicationRepository(Protocol):
    async def get(self, application_id: uuid.UUID) -> Application | None: ...
    async def save(self, application: Application) -> Application: ...
    async def parties(self, application_id: uuid.UUID) -> list[tuple[str, Party]]:
        """(role, party) pairs on the application, ordered by role."""
        ...

    async def set_parties(self, application_id: uuid.UUID, roles: dict[str, uuid.UUID]) -> None:
        """Replace the application's parties with `roles` (role -> party id)."""
        ...


class UnitOfWork(Protocol):
    parties: PartyRepository
    catalog: CatalogRepository
    needs: NeedsRepository
    objects: InsurableObjectRepository
    recommendations: RecommendationRepository
    quotes: QuoteRepository
    applications: ApplicationRepository

    async def flush(self) -> None: ...


UnitOfWorkFactory = Callable[[], AbstractAsyncContextManager[UnitOfWork]]

# ------------------------------------------------------------------------------------ external systems
# Non-2xx responses raise; a transient failure (5xx, 429, timeout) is retried by the caller.


class PartnerGateway(Protocol):
    async def match_customer(
        self, *, full_name: str, email: str, phone: str, consent_at: datetime
    ) -> dict[str, Any]: ...
    async def purchases(self, ref: str, *, consent_at: datetime) -> list[dict[str, Any]]: ...


class IdentityGateway(Protocol):
    async def send_otp(self, phone: str) -> dict[str, Any]: ...
    async def verify_otp(self, otp_request_id: str, code: str) -> dict[str, Any]: ...
    async def verify_document(
        self, *, document_type: str, document_number: str, full_name: str, date_of_birth: str | None
    ) -> dict[str, Any]: ...


class ContractGateway(Protocol):
    async def submit_application(self, application_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...


# ------------------------------------------------------------------------------------ events

EntityListener = Callable[[str, str, str], Awaitable[None]]  # (session_id, entity_type, entity_id)
