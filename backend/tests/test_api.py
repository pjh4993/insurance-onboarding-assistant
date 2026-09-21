"""HTTP API (CONTRACTS.md §3) through FastAPI's TestClient with fake externals and LLM."""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.main import Overrides, create_app
from app.services.pubsub import PING_FRAME, Broker, Event, sse_frame
from tests.conftest import FIXED_NOW
from tests.fakes import CUSTOMERS, identity_input

AGENT = {"X-Agent-Id": "agent-demo"}


@pytest.fixture
def client(settings, external, llm):
    app = create_app(settings, Overrides(transport=external.transport(), llm=llm, clock=lambda: FIXED_NOW))
    with TestClient(app) as c:
        yield c


def wait_for(client: TestClient, headers: dict, waiting_for, status: str | None = None, timeout: float = 15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        view = client.get("/api/customer/session", headers=headers).json()
        s = view["session"]
        if s["waiting_for"] == waiting_for and (status is None or s["status"] == status):
            return view
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {waiting_for}/{status}; last: {view['session']}")


def post_input(client, headers, input_type, data, path="/api/customer/session/input"):
    r = client.post(path, headers=headers, json={"type": input_type, "data": data})
    assert r.status_code == 202, r.text
    assert r.json() == {"accepted": True}


def new_session(client, market="KR", headers=None):
    r = client.post("/api/sessions", json={"market": market}, headers=headers or {})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["customer_path"] == f"/s/{body['token']}"
    return body, {"X-Session-Token": body["token"]}


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_customer_full_flow_customer_a(client):
    body, h = new_session(client, "KR", headers=AGENT)  # the console calls this with X-Agent-Id
    view = client.get("/api/customer/session", headers=h).json()
    assert view["session"]["display_name"].startswith("Unverified #")
    assert view["session"]["waiting_for"] == "IDENTITY_INFO" and view["prompt"]["waiting_for"] == "IDENTITY_INFO"
    assert view["messages"][0]["role"] == "assistant"

    post_input(client, h, "IDENTITY_INFO", identity_input("A", consent=True))
    view = wait_for(client, h, "NEEDS")
    assert view["session"]["display_name"] == CUSTOMERS["A"]["full_name"]
    assert view["session"]["stage"] == "PROFILING"

    post_input(client, h, "NEEDS", {"text": CUSTOMERS["A"]["needs_text"]})
    view = wait_for(client, h, "DECISION")
    options = view["prompt"]["options"]
    assert len(options) == 1 and options[0]["product_code"] == "KR-MOB-SWAP"
    card = options[0]
    assert card["quote"]["premium_minor"] == 9990 and card["quote"]["currency"] == "KRW"
    assert card["quote"]["billing_period"] == "MONTHLY" and card["status"] == "PROPOSED"

    # a wrong recommendation id is rejected before resuming the graph
    r = client.post(
        "/api/customer/session/input",
        headers=h,
        json={"type": "DECISION", "data": {"decision": "ACCEPT", "recommendation_id": "nope"}},
    )
    assert r.status_code == 422

    post_input(client, h, "DECISION", {"decision": "ACCEPT", "recommendation_id": card["recommendation_id"]})
    wait_for(client, h, "PARTIES")
    post_input(client, h, "PARTIES", {"text": "모두 저예요."})
    view = wait_for(client, h, "CONFIRM")
    assert view["prompt"]["summary"] == "Application summary for A."
    post_input(client, h, "CONFIRM", {"confirmed": True})
    view = wait_for(client, h, None, status="SUBMITTED")
    assert view["session"]["stage"] == "SUBMITTED" and view["prompt"] is None
    assert "SUB-2026-" in view["messages"][-1]["text"]
    roles = {m["role"] for m in view["messages"]}
    assert roles == {"assistant", "customer"}
    assert all(m["id"] and m["created_at"] for m in view["messages"])

    detail = client.get(f"/api/agent/sessions/{body['session_id']}", headers=AGENT).json()
    assert detail["entities"]["application"]["submission_ref"].startswith("SUB-2026-")
    assert detail["current_node"] is None
    party = detail["entities"]["party"]
    assert party["verification_status"] == "VERIFIED" and party["verification_method"] == "PARTNER_MATCH"
    assert "id_document_number" not in party
    assert CUSTOMERS["A"]["id_document_number"] not in str(detail)


def test_input_validation_and_auth(client):
    _, h = new_session(client, "US")
    assert client.get("/api/customer/session").status_code == 401
    assert client.get("/api/customer/session", headers={"X-Session-Token": "bad"}).status_code == 401
    # wrong type for what the session waits for
    r = client.post("/api/customer/session/input", headers=h, json={"type": "NEEDS", "data": {"text": "hi"}})
    assert r.status_code == 409
    # schema validation of data
    r = client.post("/api/customer/session/input", headers=h, json={"type": "IDENTITY_INFO", "data": {"email": "x"}})
    assert r.status_code == 422
    # customers cannot send agent resolutions
    r = client.post("/api/customer/session/input", headers=h, json={"type": "AGENT", "data": {"resolution": "END"}})
    assert r.status_code == 403
    assert client.get("/api/agent/sessions").status_code == 401
    assert client.get("/api/agent/sessions/not-a-uuid", headers=AGENT).status_code == 404


def test_agent_list_assign_and_resolve_handoff(client):
    d_body, d = new_session(client, "US")
    c_body, c = new_session(client, "US")
    post_input(client, d, "IDENTITY_INFO", identity_input("D", consent=False))
    wait_for(client, d, "OTP_CODE")
    post_input(client, d, "OTP_CODE", {"code": "000000"})
    wait_for(client, d, "AGENT", status="HANDOFF")

    sessions = client.get("/api/agent/sessions", headers=AGENT).json()["sessions"]
    ids = [s["session_id"] for s in sessions]
    assert d_body["session_id"] in ids and c_body["session_id"] in ids
    # sessions waiting for an agent come first, then the oldest activity first
    flags = [s["waiting_for"] == "AGENT" for s in sessions]
    assert flags == sorted(flags, reverse=True)
    rest = [s["last_activity_at"] for s in sessions if s["waiting_for"] != "AGENT"]
    assert rest == sorted(rest)
    d_summary = next(s for s in sessions if s["session_id"] == d_body["session_id"])
    assert d_summary["waiting_for"] == "AGENT" and d_summary["status"] == "HANDOFF"
    assert d_summary["display_name"].startswith("Unverified #")

    r = client.post(f"/api/agent/sessions/{d_body['session_id']}/assign", headers=AGENT)
    assert r.status_code == 200
    assert r.json()["assigned_agent_id"] == "agent-demo" and r.json()["mode"] == "ASSIST"

    detail = client.get(f"/api/agent/sessions/{d_body['session_id']}", headers=AGENT).json()
    assert detail["current_node"] == "await_agent"
    assert detail["entities"]["party"]["verification_attempts"] == 2
    assert detail["prompt"]["waiting_for"] == "AGENT"

    r = client.post(
        f"/api/agent/sessions/{d_body['session_id']}/input",
        headers=AGENT,
        json={"type": "AGENT", "data": {"resolution": "VERIFIED", "note": "Checked ID on a call."}},
    )
    assert r.status_code == 202
    view = wait_for(client, d, "NEEDS", status="ACTIVE")
    assert view["session"]["display_name"] == CUSTOMERS["D"]["full_name"]
    assert any(m["role"] == "agent" and m["text"] == "Checked ID on a call." for m in view["messages"])
    # the agent can also answer on the customer's behalf
    r = client.post(
        f"/api/agent/sessions/{d_body['session_id']}/input",
        headers=AGENT,
        json={"type": "NEEDS", "data": {"text": CUSTOMERS["D"]["needs_text"]}},
    )
    assert r.status_code == 202
    wait_for(client, d, "NEEDS")


async def test_broker_stream_filters_and_pings():
    broker = Broker()
    agen = broker.stream("s1", ping_seconds=0.05, initial=[sse_frame("session.updated", {"session": {"x": 1}})])
    assert (await agen.__anext__()).startswith("event: session.updated\ndata: ")
    nxt = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0)
    broker.publish(Event("other", "message.appended", {"session_id": "other"}))
    broker.publish(Event("s1", "prompt.updated", {"session_id": "s1", "prompt": None}))
    frame = await nxt
    assert frame == 'event: prompt.updated\ndata: {"session_id": "s1", "prompt": null}\n\n'
    assert await agen.__anext__() == PING_FRAME
    await agen.aclose()
    assert broker.subscriber_count == 0
