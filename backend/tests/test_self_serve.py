"""Public self-serve starts (CONTRACTS.md §3): POST /api/public/sessions, its origin and IP hash, and the
per-IP and global hourly limits counted from the DB.

The test database is shared by the whole run and every session in it was started at some fixed clock time, so
each test that relies on counts runs at its own clock time, well away from FIXED_NOW, and uses its own IPs."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app.db.models import OnboardingSession
from app.main import Overrides, create_app
from app.services.runtime import RateLimited
from onboarding_core.crypto import hmac_hex
from tests.conftest import FIXED_NOW

AGENT = {"X-Agent-Id": "agent-demo"}
PUBLIC = "/api/public/sessions"


class Clock:
    def __init__(self, now) -> None:
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def make_client(settings, external, llm):
    clients = []

    def make(clock, **overrides) -> TestClient:
        app = create_app(
            settings.model_copy(update=overrides), Overrides(transport=external.transport(), llm=llm, clock=clock)
        )
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def db(settings):
    engine = create_engine(settings.database_url)
    yield engine
    engine.dispose()


def row(db, session_id: str):
    with db.connect() as conn:
        return conn.execute(select(OnboardingSession.__table__).where(OnboardingSession.session_id == session_id)).one()


def new_ip() -> str:
    h = uuid.uuid4().hex
    return f"2001:db8::{h[:4]}:{h[4:8]}:{h[8:12]}"


def start(client, ip: str | None, market: str = "KR"):
    headers = {"X-Client-IP": ip} if ip is not None else {}
    return client.post(PUBLIC, json={"market": market}, headers=headers)


def test_self_serve_start_records_origin_and_only_an_ip_hash(make_client, db, settings):
    client = make_client(Clock(FIXED_NOW))
    ip = new_ip()
    r = client.post(PUBLIC, json={"market": "US", "locale": "ko"}, headers={"X-Client-IP": ip})
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {"session_id", "token", "customer_path"}
    assert body["customer_path"] == f"/s/{body['token']}"

    stored = row(db, body["session_id"])
    assert stored.origin == "SELF_SERVE"
    assert stored.client_ip_hash == hmac_hex(settings.session_hmac_key, ip)
    assert ip not in str(tuple(stored))

    # the customer link works exactly like an agent's, and the graph has started
    view = client.get("/api/customer/session", headers={"X-Session-Token": body["token"]}).json()
    assert view["session"]["origin"] == "SELF_SERVE" and view["session"]["locale"] == "ko"
    assert view["session"]["waiting_for"] == "INTAKE"
    assert view["messages"][0]["role"] == "assistant"

    agent_made = client.post("/api/sessions", json={"market": "KR"}, headers=AGENT).json()
    assert set(agent_made) == {"session_id", "token", "customer_path"}
    stored = row(db, agent_made["session_id"])
    assert stored.origin == "AGENT_LINK" and stored.client_ip_hash is None

    summaries = {s["session_id"]: s for s in client.get("/api/agent/sessions", headers=AGENT).json()["sessions"]}
    assert summaries[body["session_id"]]["origin"] == "SELF_SERVE"
    assert summaries[agent_made["session_id"]]["origin"] == "AGENT_LINK"
    detail = client.get(f"/api/agent/sessions/{body['session_id']}", headers=AGENT).json()
    assert detail["session"]["origin"] == "SELF_SERVE"


def test_self_serve_validates_the_body_like_agent_links(make_client):
    client = make_client(Clock(FIXED_NOW))
    assert client.post(PUBLIC, json={"market": "JP"}, headers={"X-Client-IP": new_ip()}).status_code == 422
    assert client.post(PUBLIC, json={"market": "KR", "locale": "fr"}).status_code == 422


def test_per_ip_limit_returns_429_with_retry_after(make_client, caplog):
    clock = Clock(FIXED_NOW + timedelta(days=10))
    client = make_client(clock, self_serve_per_ip_per_hour=3)
    ip, other = new_ip(), new_ip()
    assert start(client, ip).status_code == 201
    clock.now += timedelta(minutes=10)
    assert start(client, ip).status_code == 201
    assert start(client, ip).status_code == 201

    caplog.set_level(logging.WARNING, logger="app.services.runtime")
    r = start(client, ip)
    assert r.status_code == 429
    # the oldest counted session, started 10 minutes ago, leaves the window in 50 minutes
    assert r.json() == {"detail": "rate_limited", "retry_after": 3000}
    assert r.headers["Retry-After"] == "3000"
    limited = [rec for rec in caplog.records if rec.getMessage() == "self-serve rate limited"]
    assert [rec.scope for rec in limited] == ["ip"]
    assert all(ip not in str(vars(rec)) for rec in caplog.records)

    # different IPs are independent
    assert start(client, other).status_code == 201

    # the window slides: once the oldest leaves it, one more start is allowed
    clock.now += timedelta(minutes=50)
    assert start(client, ip).status_code == 201
    assert start(client, ip).status_code == 429


def test_missing_client_ip_shares_one_bucket(make_client):
    client = make_client(Clock(FIXED_NOW + timedelta(days=20)), self_serve_per_ip_per_hour=2)
    assert start(client, None).status_code == 201
    assert start(client, "  ").status_code == 201
    r = start(client, None)
    assert r.status_code == 429 and r.json()["retry_after"] == 3600


def test_global_limit_and_agent_links_do_not_count(make_client, caplog):
    # The latest clock of any test here, so no other test's sessions fall inside this window.
    clock = Clock(FIXED_NOW + timedelta(days=30))
    client = make_client(clock, self_serve_per_hour=3)

    # agent-created sessions never count toward the self-serve limits
    for _ in range(4):
        assert client.post("/api/sessions", json={"market": "KR"}, headers=AGENT).status_code == 201

    for _ in range(3):
        assert start(client, new_ip()).status_code == 201
    caplog.set_level(logging.WARNING, logger="app.services.runtime")
    r = start(client, new_ip())
    assert r.status_code == 429
    assert r.json() == {"detail": "rate_limited", "retry_after": 3600}
    assert r.headers["Retry-After"] == "3600"
    assert [rec.scope for rec in caplog.records if rec.getMessage() == "self-serve rate limited"] == ["global"]

    # agent links are not limited by it either
    assert client.post("/api/sessions", json={"market": "US"}, headers=AGENT).status_code == 201


async def test_concurrent_starts_cannot_share_the_last_slot(runtime):
    runtime.settings = runtime.settings.model_copy(update={"self_serve_per_ip_per_hour": 2})
    ip_hash = runtime.client_ip_hash(new_ip())

    results = await asyncio.gather(
        *(runtime.create_session("KR", origin="SELF_SERVE", client_ip_hash=ip_hash) for _ in range(5)),
        return_exceptions=True,
    )
    assert sum(isinstance(r, tuple) for r in results) == 2
    assert sum(isinstance(r, RateLimited) and r.scope == "ip" for r in results) == 3
