"""Engine, session factory and idempotent bootstrap (schemas, tables, catalog seed)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import SCHEMAS, Base, EligibilityRule, Product, TargetMarket
from app.domain.catalog_seed import PRODUCTS
from app.util import catalog_uuid

SEED_EFFECTIVE_DATE = date(2026, 1, 1)


def make_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Create schemas and tables, then upsert the catalog seed. Safe to run on every start."""
    async with engine.begin() as conn:
        # Serialise concurrent starts (several replicas) on one advisory lock.
        await conn.execute(text("SELECT pg_advisory_xact_lock(724001)"))
        for schema in SCHEMAS:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.run_sync(Base.metadata.create_all)
    await seed_catalog(make_sessionmaker(engine))


async def seed_catalog(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as s, s.begin():
        for spec in PRODUCTS:
            code = spec["product_code"]
            await s.merge(
                Product(
                    product_code=code,
                    product_type=spec["product_type"],
                    marketing_name=spec["marketing_name"],
                    insurable_object_type=spec["insurable_object_type"],
                    coverages=spec["coverages"],
                    rating=spec["rating"],
                    billing_period=spec["billing_period"],
                    currency=spec["currency"],
                    jurisdictions=spec["jurisdictions"],
                    sale_effective_date=SEED_EFFECTIVE_DATE,
                    sale_expiration_date=None,
                    term_rule=spec["term_rule"],
                    required_application_fields=spec["required_application_fields"],
                    status="ACTIVE",
                )
            )
        await s.flush()
        for spec in PRODUCTS:
            code = spec["product_code"]
            rule_ids = []
            for rule in spec["rules"]:
                rule_id = catalog_uuid("rule", code, rule["failure_reason_code"], rule["attribute"])
                rule_ids.append(rule_id)
                await s.merge(EligibilityRule(rule_id=rule_id, product_code=code, **rule))
            await s.execute(
                delete(EligibilityRule).where(
                    EligibilityRule.product_code == code, EligibilityRule.rule_id.not_in(rule_ids)
                )
            )
            tm_ids = []
            for i, tm in enumerate(spec["target_markets"]):
                tm_id = catalog_uuid("tm", code, str(i))
                tm_ids.append(tm_id)
                await s.merge(TargetMarket(target_market_id=tm_id, product_code=code, **tm))
            await s.execute(
                delete(TargetMarket).where(
                    TargetMarket.product_code == code, TargetMarket.target_market_id.not_in(tm_ids)
                )
            )
