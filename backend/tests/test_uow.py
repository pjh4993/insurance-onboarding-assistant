"""The SQLAlchemy unit of work behind `onboarding_core.ports`: core dataclasses map onto the tables,
and `save` is an idempotent upsert that leaves server-managed columns alone."""

from __future__ import annotations

import uuid

import pytest

from app.db.engine import init_db, make_engine, make_sessionmaker
from app.db.uow import uow_factory
from onboarding_core.needs.models import InsurableObject
from onboarding_core.party.models import Party


@pytest.fixture
async def uow(settings):
    engine = make_engine(settings.database_url)
    await init_db(engine)
    yield uow_factory(make_sessionmaker(engine))
    await engine.dispose()


async def test_resaving_an_entity_keeps_server_defaults(uow):
    party_id, obj_id = uuid.uuid4(), uuid.uuid4()
    async with uow() as u:
        await u.parties.add(Party(party_id=party_id))
        await u.flush()
        await u.objects.save(
            InsurableObject(
                insurable_object_id=obj_id,
                owner_party_id=party_id,
                object_type="DEVICE",
                source="PARTNER",
                attributes={"model": "A"},
            )
        )
    async with uow() as u:
        created = (await u.objects.get(obj_id)).created_at
        assert created is not None
    # A node re-run writes the same id again: an upsert, not a NULL over created_at.
    async with uow() as u:
        await u.objects.save(
            InsurableObject(
                insurable_object_id=obj_id,
                owner_party_id=party_id,
                object_type="DEVICE",
                source="PARTNER",
                attributes={"model": "B"},
            )
        )
    async with uow() as u:
        obj = await u.objects.get(obj_id)
        assert obj.attributes == {"model": "B"} and obj.created_at == created
        party = await u.parties.get(party_id)
        assert party.verification_status == "UNVERIFIED" and party.created_at is not None


async def test_changes_to_tracked_entities_commit_or_roll_back(uow):
    party_id = uuid.uuid4()
    async with uow() as u:
        await u.parties.add(Party(party_id=party_id))
    async with uow() as u:
        (await u.parties.get(party_id)).full_name = "Kim"
    with pytest.raises(RuntimeError):
        async with uow() as u:
            (await u.parties.get(party_id)).full_name = "Lee"
            raise RuntimeError("node failed")
    async with uow() as u:
        assert (await u.parties.get(party_id)).full_name == "Kim"
