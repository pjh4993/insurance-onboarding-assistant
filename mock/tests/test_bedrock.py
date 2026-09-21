"""Converse route through TestClient: fixture choice, response shape, faults."""

import pytest

from mock_server.fixtures import NEEDS_FIELDS

MODEL = "global.anthropic.claude-sonnet-4-6"


def tool_config(name):
    return {"tools": [{"toolSpec": {"name": name, "inputSchema": {"json": {"type": "object"}}}}]}


def converse(client, text, tool=None, model=MODEL, system=None):
    body = {"messages": [{"role": "user", "content": [{"text": text}]}]}
    if tool:
        body["toolConfig"] = tool_config(tool)
    if system:
        body["system"] = [{"text": system}]
    r = client.post(f"/model/{model}/converse", json=body)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/json")
    return r.json()


def tool_input(resp, name):
    assert resp["stopReason"] == "tool_use"
    (block,) = resp["output"]["message"]["content"]
    assert block["toolUse"]["name"] == name
    assert block["toolUse"]["toolUseId"].startswith("tooluse_")
    return block["toolUse"]["input"]


def test_shape_and_usage(client):
    resp = converse(client, "hello")
    assert resp["stopReason"] == "end_turn"
    assert resp["output"]["message"]["role"] == "assistant"
    assert resp["output"]["message"]["content"][0]["text"]
    usage = resp["usage"]
    assert usage["totalTokens"] == usage["inputTokens"] + usage["outputTokens"]
    assert isinstance(resp["metrics"]["latencyMs"], int)


def test_text_reply_follows_market(client):
    assert "확인" in converse(client, "고객: 김하늘")["output"]["message"]["content"][0]["text"]
    assert "Thanks" in converse(client, "Customer: Jane Doe")["output"]["message"]["content"][0]["text"]


@pytest.mark.parametrize(
    ("name", "age", "objective"),
    [
        ("김하늘", "AGE_30_39", "PROTECT_DEVICE"),
        ("이서준", "AGE_40_49", "TRAVEL_COVER"),
        ("Jane Doe", "AGE_30_39", "PROTECT_DEVICE"),
        ("John Roe", None, "PROTECT_DEVICE"),
    ],
)
def test_needs_by_customer(client, name, age, objective):
    data = tool_input(
        converse(client, "extract needs", "NeedsExtraction", system=f"Customer: {name}"), "NeedsExtraction"
    )
    assert set(NEEDS_FIELDS) | {"missing_fields"} == set(data)
    assert data["age_range"] == age
    assert objective in data["objectives"]


def test_needs_matches_seed_needs_text_without_name(client):
    text = (
        "마흔 살 회사원이에요. 다음 달 일본 여행 가는데 여행자보험이 필요해요. "
        "10월 3일 출발, 10월 7일 귀국입니다."
    )
    data = tool_input(converse(client, text, "NeedsExtraction"), "NeedsExtraction")
    assert data["trip"]["destination_countries"] == ["JP"]


def test_needs_generic_fallback(client):
    data = tool_input(
        converse(client, "I want cover for my tablet and a trip", "NeedsExtraction"), "NeedsExtraction"
    )
    assert data["objectives"] == ["PROTECT_DEVICE", "TRAVEL_COVER"]
    assert data["device"]["device_category"] == "TABLET"
    assert "age_range" in data["missing_fields"]


def test_snake_case_tool_name_is_accepted(client):
    data = tool_input(converse(client, "Jane Doe", "needs_extraction"), "needs_extraction")
    assert data["occupation"] == "Nurse"


def test_rationale_echoes_ids(client):
    prompt = (
        "Customer: 김하늘\nRecommendations:\n"
        '[{"recommendation_id": "rec-1", "product_code": "DEVICE_PROTECTION_STD", '
        '"marketing_name": "Phone Care", '
        '"product_type": "DEVICE_PROTECTION", "eligibility_result": "ELIGIBLE"},\n'
        '{"recommendation_id": "rec-2", "product_code": "TRAVEL_BASIC", "product_type": "TRAVEL", '
        '"eligibility_result": "INELIGIBLE"}]\n'
        "- recommendation_id: 3f1c2a9e-0000-4000-8000-000000000001 (EXTENDED_WARRANTY)"
    )
    data = tool_input(converse(client, prompt, "RecommendationRationale"), "RecommendationRationale")
    ids = [item["recommendation_id"] for item in data["items"]]
    assert ids == ["rec-1", "rec-2", "3f1c2a9e-0000-4000-8000-000000000001"]
    assert all(item["rationale"] for item in data["items"])
    assert "Galaxy S26" in data["items"][0]["rationale"]
    assert "비교용" in data["items"][1]["rationale"]


def test_rationale_without_ids(client):
    assert tool_input(converse(client, "nothing", "RecommendationRationale"), "RecommendationRationale") == {
        "items": []
    }


def test_parties_answers_summary(client):
    parties = tool_input(converse(client, "Jane Doe", "PartiesExtraction"), "PartiesExtraction")
    assert parties == {"all_self": True, "parties": []}
    answers = tool_input(converse(client, "김하늘", "AnswersExtraction"), "AnswersExtraction")
    assert answers["answers"]["device_model"] == "Galaxy S26" and answers["missing_fields"] == []
    generic = tool_input(converse(client, "unknown person", "AnswersExtraction"), "AnswersExtraction")
    assert generic == {"answers": {}, "missing_fields": []}
    summary = tool_input(converse(client, "John Roe", "ApplicationSummary"), "ApplicationSummary")
    assert "John Roe" in summary["summary"]


def test_tool_choice_selects_tool(client):
    body = {
        "messages": [{"role": "user", "content": [{"text": "Jane Doe"}]}],
        "toolConfig": {
            "tools": tool_config("NeedsExtraction")["tools"] + tool_config("ApplicationSummary")["tools"],
            "toolChoice": {"tool": {"name": "ApplicationSummary"}},
        },
    }
    resp = client.post(f"/model/{MODEL}/converse", json=body).json()
    assert resp["output"]["message"]["content"][0]["toolUse"]["name"] == "ApplicationSummary"


@pytest.mark.parametrize(
    "model",
    [
        "global.anthropic.claude-haiku-4-5-20251001-v1:0",
        "global.anthropic.claude-haiku-4-5-20251001-v1%3A0",
        "arn%3Aaws%3Abedrock%3Aap-northeast-2%3A123456789012%3Ainference-profile%2Fglobal.x",
    ],
)
def test_model_ids_with_colon_and_slash(client, model):
    assert converse(client, "hi", model=model)["stopReason"] == "end_turn"


def test_invalid_body(client):
    r = client.post(f"/model/{MODEL}/converse", json={"foo": 1})
    assert r.status_code == 400
    assert r.headers["x-amzn-errortype"].startswith("ValidationException")


@pytest.mark.parametrize(
    ("kind", "status", "code"),
    [
        ("429", 429, "ThrottlingException"),
        ("500", 500, "InternalServerException"),
        ("timeout", 504, "ModelTimeoutException"),
    ],
)
def test_bedrock_faults(client, kind, status, code):
    client.post("/_mock/faults", json={"target": "bedrock", "kind": kind, "count": 1, "delay_seconds": 0.01})
    body = {"messages": [{"role": "user", "content": [{"text": "hi"}]}]}
    r = client.post(f"/model/{MODEL}/converse", json=body)
    assert r.status_code == status
    assert r.headers["x-amzn-errortype"].split(":")[0] == code
    assert r.json()["message"]
    assert client.post(f"/model/{MODEL}/converse", json=body).status_code == 200
