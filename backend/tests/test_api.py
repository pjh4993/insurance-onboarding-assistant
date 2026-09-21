"""HTTP API (CONTRACTS.md §3) through FastAPI's TestClient with fake externals and LLM."""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.main import Overrides, create_app
from app.services.pubsub import PING_FRAME, Event, InMemoryBroker, sse_frame
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


def test_session_locale_defaults_to_market_and_switches_the_next_reply(client):
    body, h = new_session(client, "KR")
    view = client.get("/api/customer/session", headers=h).json()
    assert view["session"]["locale"] == "ko"
    assert view["messages"][0]["text"].startswith("안녕하세요")

    r = client.put("/api/customer/session/locale", headers=h, json={"locale": "en"})
    assert r.status_code == 200, r.text
    assert r.json()["locale"] == "en" and r.json()["market"] == "KR"
    assert client.put("/api/customer/session/locale", headers=h, json={"locale": "fr"}).status_code == 422
    assert client.put("/api/customer/session/locale", json={"locale": "en"}).status_code == 401

    # messages already sent stay in Korean; the next reply follows the new language, the market stays KR
    post_input(client, h, "IDENTITY_INFO", identity_input("A", consent=True))
    view = wait_for(client, h, "NEEDS")
    assert view["messages"][0]["text"].startswith("안녕하세요")
    assert view["prompt"]["message"].isascii(), view["prompt"]["message"]

    # an agent can set it too
    r = client.put(f"/api/agent/sessions/{body['session_id']}/locale", headers=AGENT, json={"locale": "ko"})
    assert r.status_code == 200 and r.json()["locale"] == "ko"


def test_languages_come_from_the_agent_config(client):
    assert client.get("/api/languages").json() == {
        "languages": [{"code": "ko", "name": "Korean"}, {"code": "en", "name": "English"}],
        "default": "en",
    }
    assert client.post("/api/sessions", json={"market": "KR", "locale": "ja"}).status_code == 422
    assert client.post("/api/sessions", json={"market": "KR", "locale": "not a code"}).status_code == 422


def bundle_in_japanese(tmp_path):
    """The baseline bundle plus Japanese: a new language is a new (minor) version of the bundle."""
    import json
    import shutil
    from pathlib import Path

    from onboarding_agent.config import BUNDLED, default_bundle, load_bundle

    target = tmp_path / "1.1.0"
    shutil.copytree(Path(str(BUNDLED)) / default_bundle().version, target)
    config = json.loads((target / "config.json").read_text())
    config["version"] = "1.1.0"
    config["languages"]["ja"] = {"name": "Japanese"}
    for entry in [*config["labels"].values(), *config["billing_periods"].values()]:
        entry["ja"] = entry["en"]
    (target / "config.json").write_text(json.dumps(config, ensure_ascii=False))
    for path in config["flows"].values():
        flow = json.loads((target / path).read_text())
        for key, entry in flow["copy"].items():
            entry["ja"] = "こんにちは！保険の加入をお手伝いします。" if key == "greeting" else entry["en"]
        (target / path).write_text(json.dumps(flow, ensure_ascii=False))
    return load_bundle(str(tmp_path))


def test_a_language_added_to_the_bundle_can_be_used(settings, external, llm, tmp_path):
    bundle = bundle_in_japanese(tmp_path)
    app = create_app(
        settings, Overrides(transport=external.transport(), llm=llm, clock=lambda: FIXED_NOW, bundle=bundle)
    )
    with TestClient(app) as client:
        assert [lang["code"] for lang in client.get("/api/languages").json()["languages"]] == ["ko", "en", "ja"]
        r = client.post("/api/sessions", json={"market": "KR", "locale": "ja"})
        assert r.status_code == 201, r.text
        view = client.get("/api/customer/session", headers={"X-Session-Token": r.json()["token"]}).json()
        assert view["session"]["locale"] == "ja"
        assert view["messages"][0]["text"] == "こんにちは！保険の加入をお手伝いします。"


def test_a_bad_config_bundle_stops_startup_and_says_why(settings, external, llm, tmp_path, caplog):
    import json
    import shutil
    from pathlib import Path

    from onboarding_agent.config import BUNDLED, ConfigError, default_bundle

    bad = tmp_path / "1.0.1"
    shutil.copytree(Path(str(BUNDLED)) / default_bundle().version, bad)
    config = json.loads((bad / "config.json").read_text())
    config["version"] = "1.0.1"
    config["models"]["default"]["model_id"] = "anthropic.claude-opus-9"
    (bad / "config.json").write_text(json.dumps(config))
    settings = settings.model_copy(
        update={"agent_config_uri": str(tmp_path), "llm_allowed_model_ids": "global.anthropic.claude-sonnet-4-6"}
    )
    app = create_app(settings, Overrides(transport=external.transport(), llm=llm, clock=lambda: FIXED_NOW))
    with pytest.raises(ConfigError), TestClient(app):
        pass
    rejected = [r for r in caplog.records if r.getMessage() == "agent config rejected"]
    assert rejected and "anthropic.claude-opus-9 is not allowed here" in getattr(rejected[0], "agent_config.problems")


def test_session_locale_can_be_chosen_at_creation(client):
    r = client.post("/api/sessions", json={"market": "US", "locale": "ko"})
    assert r.status_code == 201, r.text
    view = client.get("/api/customer/session", headers={"X-Session-Token": r.json()["token"]}).json()
    assert view["session"]["locale"] == "ko" and view["session"]["market"] == "US"
    assert view["messages"][0]["text"].startswith("안녕하세요")


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
    broker = InMemoryBroker()
    agen = broker.stream("s1", ping_seconds=0.05, initial=[sse_frame("session.updated", {"session": {"x": 1}})])
    assert (await agen.__anext__()).startswith("event: session.updated\ndata: ")
    nxt = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0)
    await broker.publish(Event("other", "message.appended", {"session_id": "other"}))
    await broker.publish(Event("s1", "prompt.updated", {"session_id": "s1", "prompt": None}))
    frame = await nxt
    assert frame == 'event: prompt.updated\ndata: {"session_id": "s1", "prompt": null}\n\n'
    assert await agen.__anext__() == PING_FRAME
    await agen.aclose()
    assert broker.subscriber_count == 0
