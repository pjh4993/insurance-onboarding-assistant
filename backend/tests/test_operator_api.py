"""Operator API: browse agent config versions, validate and publish drafts, restart the backend."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import Overrides, create_app
from tests.conftest import FIXED_NOW

OPERATOR = {"X-Operator-Id": "operator-demo"}


class FakeECS:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def update_service(self, **kwargs):
        self.calls.append(kwargs)
        return {"service": {"serviceName": kwargs["service"]}}


@pytest.fixture
def ecs():
    return FakeECS()


@pytest.fixture
def operator_client(settings, external, llm, ecs, tmp_path):
    settings = settings.model_copy(
        update={
            "agent_config_uri": str(tmp_path / "agent-config"),
            "agent_config_seed": True,
            "backend_ecs_cluster": "onboarding-develop",
            "backend_ecs_service": "onboarding-develop-backend",
        }
    )
    app = create_app(settings, Overrides(transport=external.transport(), llm=llm, clock=lambda: FIXED_NOW, ecs=ecs))
    with TestClient(app) as c:
        yield c


def edited_draft(client, version="1.2.0"):
    files = client.get(f"/api/operator/config/versions/{version}", headers=OPERATOR).json()["files"]
    profiling = json.loads(files["flows/profiling.json"])
    profiling["copy"]["needs_complete"]["en"] = "Thanks! Checking what fits you now."
    files["flows/profiling.json"] = json.dumps(profiling, ensure_ascii=False, indent=2)
    return files


def test_operator_endpoints_need_an_operator(operator_client):
    assert operator_client.get("/api/operator/config").status_code == 401
    assert operator_client.post("/api/operator/restart").status_code == 401


def test_status_and_versions(operator_client):
    status = operator_client.get("/api/operator/config", headers=OPERATOR).json()
    assert status["live"]["version"] == "1.2.0" and status["next"] == "1.2.0"
    assert status["publishable"] and status["restartable"] and not status["restart_needed"]

    versions = operator_client.get("/api/operator/config/versions", headers=OPERATOR).json()["versions"]
    assert [(v["version"], v["live"], v["latest"]) for v in versions] == [
        ("1.2.0", True, True),
        ("1.1.0", False, False),
        ("1.0.0", False, False),
    ]
    assert {v["release"]["published_by"] for v in versions} == {"baseline"}

    detail = operator_client.get("/api/operator/config/versions/1.2.0", headers=OPERATOR).json()
    assert detail["problems"] == []
    assert set(detail["files"]) >= {"config.json", "flows/profiling.json"} and "release.json" not in detail["files"]
    assert detail["summary"]["models"][0]["model_id"] == "global.anthropic.claude-sonnet-4-6"
    assert detail["summary"]["nodes"]["assess_needs"] == "default"
    # a version written for older agent code stays browsable, with what this code would miss in it
    old = operator_client.get("/api/operator/config/versions/1.0.0", headers=OPERATOR).json()
    assert old["summary"] is None and old["problems"] and "config.json" in old["files"]
    assert operator_client.get("/api/operator/config/versions/9.9.9", headers=OPERATOR).status_code == 404
    assert operator_client.get("/api/operator/config/versions/latest", headers=OPERATOR).status_code == 404


def test_validate_reports_every_problem(operator_client):
    files = edited_draft(operator_client)
    assert operator_client.post("/api/operator/config/validate", headers=OPERATOR, json={"files": files}).json()["ok"]

    identity = json.loads(files["flows/identity.json"])
    identity["copy"]["otp_sent"]["en"] = "Sent to {phone_number}"
    files["flows/identity.json"] = json.dumps(identity)
    body = operator_client.post("/api/operator/config/validate", headers=OPERATOR, json={"files": files}).json()
    assert not body["ok"] and any("phone_number" in p for p in body["problems"])

    r = operator_client.post(
        "/api/operator/config/validate", headers=OPERATOR, json={"files": {**files, "../escape.json": "{}"}}
    )
    assert r.status_code == 422


def test_publish_bumps_and_restart_rolls_the_backend(operator_client, ecs):
    files = edited_draft(operator_client)
    r = operator_client.post(
        "/api/operator/config/versions",
        headers=OPERATOR,
        json={"files": files, "notes": "friendlier wording", "bump": "minor"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["version"] == "1.3.0"
    release = r.json()["release"]
    assert release["published_by"] == "operator-demo" and release["based_on"] == "1.2.0"
    assert release["notes"] == "friendlier wording" and release["via"] == "operator-console"

    # the same draft again is the next patch; the backend keeps running 1.2.0 until it restarts
    assert (
        operator_client.post("/api/operator/config/versions", headers=OPERATOR, json={"files": files}).json()["version"]
        == "1.3.1"
    )
    status = operator_client.get("/api/operator/config", headers=OPERATOR).json()
    assert status["live"]["version"] == "1.2.0" and status["next"] == "1.3.1" and status["restart_needed"]

    broken = {**files, "config.json": files["config.json"].replace('"temperature": 0', '"temperature": 7')}
    r = operator_client.post("/api/operator/config/versions", headers=OPERATOR, json={"files": broken})
    assert r.status_code == 422 and any("temperature" in p for p in r.json()["detail"]["problems"])

    r = operator_client.post("/api/operator/restart", headers=OPERATOR)
    assert r.status_code == 202 and r.json()["requested_by"] == "operator-demo"
    assert ecs.calls == [
        {"cluster": "onboarding-develop", "service": "onboarding-develop-backend", "forceNewDeployment": True}
    ]


def test_without_a_config_repo_the_console_only_reads(settings, external, llm):
    app = create_app(settings, Overrides(transport=external.transport(), llm=llm, clock=lambda: FIXED_NOW))
    with TestClient(app) as client:
        status = client.get("/api/operator/config", headers=OPERATOR).json()
        assert not status["publishable"] and not status["restartable"]
        files = client.get("/api/operator/config/versions/1.2.0", headers=OPERATOR).json()["files"]
        r = client.post("/api/operator/config/versions", headers=OPERATOR, json={"files": files})
        assert r.status_code == 409
        assert client.post("/api/operator/restart", headers=OPERATOR).status_code == 409


def test_graph_shows_the_agent_loop_and_what_each_node_reads(operator_client):
    graph = operator_client.get("/api/operator/graph", headers=OPERATOR).json()
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert nodes["assess_needs"]["kind"] == "llm" and "llm:assess_needs.instructions" in nodes["assess_needs"]["reads"]
    assert nodes["greet"]["reads"] == ["copy:conversation.greeting"]
    assert {"source": "greet", "target": "ask_customer", "kind": "route"} in graph["edges"]
