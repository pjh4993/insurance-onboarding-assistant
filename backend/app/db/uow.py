"""SQLAlchemy adapter for `onboarding_core.ports.UnitOfWork`: one AsyncSession per unit of work,
committed when the block exits cleanly and rolled back otherwise."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import (
    Application,
    ApplicationParty,
    EligibilityRule,
    InsurableObject,
    NeedsAssessment,
    Party,
    Product,
    Quote,
    Recommendation,
    TargetMarket,
)
from onboarding_core.ports import UnitOfWorkFactory


@dataclass
class _Repo:
    s: AsyncSession


class PartyRepo(_Repo):
    async def get(self, party_id: uuid.UUID) -> Party | None:
        return await self.s.get(Party, party_id)

    async def add(self, party: Party) -> None:
        self.s.add(party)

    async def save(self, party: Party) -> Party:
        return await self.s.merge(party)


class CatalogRepo(_Repo):
    async def product(self, product_code: str) -> Product | None:
        return await self.s.get(Product, product_code)

    async def active_products(self, market: str) -> list[Product]:
        rows = await self.s.execute(
            select(Product)
            .where(Product.status == "ACTIVE", Product.jurisdictions.any(market))
            .order_by(Product.product_code)
        )
        return list(rows.scalars())

    async def rules(self) -> list[EligibilityRule]:
        return list((await self.s.execute(select(EligibilityRule))).scalars())

    async def target_markets(self) -> list[TargetMarket]:
        return list((await self.s.execute(select(TargetMarket))).scalars())


class NeedsRepo(_Repo):
    async def get(self, needs_assessment_id: uuid.UUID) -> NeedsAssessment | None:
        return await self.s.get(NeedsAssessment, needs_assessment_id)

    async def add(self, needs: NeedsAssessment) -> None:
        self.s.add(needs)

    async def latest_version(self, party_id: uuid.UUID) -> int:
        return await self.s.scalar(
            select(func.coalesce(func.max(NeedsAssessment.version), 0)).where(NeedsAssessment.party_id == party_id)
        )


class InsurableObjectRepo(_Repo):
    async def get(self, insurable_object_id: uuid.UUID) -> InsurableObject | None:
        return await self.s.get(InsurableObject, insurable_object_id)

    async def list(self, ids: Iterable[uuid.UUID]) -> list[InsurableObject]:
        rows = await self.s.execute(select(InsurableObject).where(InsurableObject.insurable_object_id.in_(list(ids))))
        return list(rows.scalars())

    async def save(self, obj: InsurableObject) -> InsurableObject:
        return await self.s.merge(obj)


class RecommendationRepo(_Repo):
    async def get(self, recommendation_id: uuid.UUID) -> Recommendation | None:
        return await self.s.get(Recommendation, recommendation_id)

    async def list(self, ids: Iterable[uuid.UUID]) -> list[Recommendation]:
        rows = await self.s.execute(select(Recommendation).where(Recommendation.recommendation_id.in_(list(ids))))
        return list(rows.scalars())

    async def save(self, rec: Recommendation) -> Recommendation:
        return await self.s.merge(rec)


class QuoteRepo(_Repo):
    async def get(self, quote_id: uuid.UUID) -> Quote | None:
        return await self.s.get(Quote, quote_id)

    async def save(self, quote: Quote) -> Quote:
        return await self.s.merge(quote)


class ApplicationRepo(_Repo):
    async def get(self, application_id: uuid.UUID) -> Application | None:
        return await self.s.get(Application, application_id)

    async def save(self, application: Application) -> Application:
        return await self.s.merge(application)

    async def parties(self, application_id: uuid.UUID) -> list[tuple[str, Party]]:
        rows = await self.s.execute(
            select(ApplicationParty.role, Party)
            .join(Party, Party.party_id == ApplicationParty.party_id)
            .where(ApplicationParty.application_id == application_id)
            .order_by(ApplicationParty.role)
        )
        return [(role, p) for role, p in rows.all()]

    async def set_parties(self, application_id: uuid.UUID, roles: dict[str, uuid.UUID]) -> None:
        await self.s.execute(delete(ApplicationParty).where(ApplicationParty.application_id == application_id))
        await self.s.flush()
        for role, party_id in roles.items():
            self.s.add(ApplicationParty(application_id=application_id, party_id=party_id, role=role))


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.parties = PartyRepo(session)
        self.catalog = CatalogRepo(session)
        self.needs = NeedsRepo(session)
        self.objects = InsurableObjectRepo(session)
        self.recommendations = RecommendationRepo(session)
        self.quotes = QuoteRepo(session)
        self.applications = ApplicationRepo(session)

    async def flush(self) -> None:
        await self.session.flush()


def uow_factory(sessionmaker: async_sessionmaker[AsyncSession]) -> UnitOfWorkFactory:
    @asynccontextmanager
    async def open_uow() -> AsyncIterator[SqlAlchemyUnitOfWork]:
        async with sessionmaker() as s, s.begin():
            yield SqlAlchemyUnitOfWork(s)

    return open_uow
