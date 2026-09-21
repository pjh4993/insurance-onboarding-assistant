"""Alembic migrations: the models match head, and a database built by create_all before migrations existed is
stamped at the baseline and upgraded. Each test gets its own database next to the shared test database."""

from __future__ import annotations

import uuid

import psycopg
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from app.db import migrate
from app.db.engine import init_db, make_engine
from app.db.models import metadata
from tests.conftest import _admin_conninfo


@pytest.fixture
def fresh_url(database_url):
    admin, base = _admin_conninfo(database_url)
    name = f"{base}_mig_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    yield database_url.rsplit("/", 1)[0] + f"/{name}"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


async def test_models_match_the_migrated_schema(fresh_url):
    engine = make_engine(fresh_url)
    await init_db(engine)
    await engine.dispose()

    with create_engine(fresh_url).connect() as conn:
        ctx = MigrationContext.configure(
            conn,
            opts={
                "include_schemas": True,
                "include_name": migrate.include_name,
                "include_object": migrate.include_object,
            },
        )
        assert compare_metadata(ctx, metadata) == []


async def test_a_pre_migration_database_is_stamped_and_upgraded(fresh_url):
    # Build what create_all left behind: the baseline tables, one KR session, and no alembic_version.
    sync = create_engine(fresh_url)
    with sync.begin() as conn:
        command.upgrade(migrate.alembic_config(conn), migrate.BASELINE)
        conn.execute(text("DROP TABLE alembic_version"))
        party = uuid.uuid4()
        conn.execute(
            text(
                "INSERT INTO domain.party (party_id, party_type, verification_status, verification_attempts) "
                "VALUES (:p, 'PERSON', 'UNVERIFIED', 0)"
            ),
            {"p": party},
        )
        conn.execute(
            text(
                "INSERT INTO domain.onboarding_session (session_id, thread_id, party_id, market, token_hmac, "
                "token_expires_at, status, last_stage, mode, started_at, last_activity_at) VALUES "
                "(:s, :s, :p, 'KR', 'h', now(), 'ACTIVE', 'IDENTITY', 'AUTO', now(), now())"
            ),
            {"s": uuid.uuid4(), "p": party},
        )

    engine = make_engine(fresh_url)
    await init_db(engine)
    await engine.dispose()

    with sync.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
        assert conn.scalar(text("SELECT locale FROM domain.onboarding_session")) == "ko"
        assert conn.scalar(text("SELECT origin FROM domain.onboarding_session")) == "AGENT_LINK"
        assert conn.scalar(text("SELECT client_ip_hash FROM domain.onboarding_session")) is None
    sync.dispose()
