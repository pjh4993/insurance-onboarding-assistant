"""The mock served by real uvicorn, called through boto3 and langchain-aws with dummy credentials."""

from typing import Literal

import boto3
import botocore.exceptions
import httpx
import pytest
from botocore.config import Config
from langchain_aws import ChatBedrockConverse
from pydantic import BaseModel

REGION = "ap-northeast-2"
SONNET = "global.anthropic.claude-sonnet-4-6"
HAIKU = "global.anthropic.claude-haiku-4-5-20251001-v1:0"


class NeedsExtraction(BaseModel):
    age_range: (
        Literal["AGE_UNDER_19", "AGE_19_29", "AGE_30_39", "AGE_40_49", "AGE_50_64", "AGE_65_PLUS"] | None
    )
    occupation: str | None
    residence_country: str | None  # ISO 3166-1 alpha-2
    existing_coverage: list[dict] = []  # {product_type, insurer_name, expires_on}
    objectives: list[Literal["PROTECT_DEVICE", "TRAVEL_COVER", "EXTEND_WARRANTY", "REDUCE_PREMIUM"]] = []
    device: dict | None  # {device_category, manufacturer, model, purchase_date, purchase_price_minor}
    trip: dict | None  # {destination_countries, departure_date, return_date, trip_cost_minor}
    missing_fields: list[str] = []  # NAMES of fields above that are still unknown


class RecommendationRationale(BaseModel):
    items: list[dict]


class PartiesExtraction(BaseModel):
    all_self: bool
    parties: list[dict] = []


class AnswersExtraction(BaseModel):
    answers: dict
    missing_fields: list[str] = []


class ApplicationSummary(BaseModel):
    summary: str


@pytest.fixture(autouse=True)
def _dummy_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "mock")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "mock")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)


def runtime(url, **config):
    return boto3.client(
        "bedrock-runtime", endpoint_url=url, region_name=REGION, config=Config(**config) if config else None
    )


def llm(url, model=SONNET):
    return ChatBedrockConverse(model=model, endpoint_url=url, region_name=REGION)


def test_boto3_converse_text(live_url):
    resp = runtime(live_url).converse(
        modelId=SONNET, messages=[{"role": "user", "content": [{"text": "Hi, I'm Jane Doe"}]}]
    )
    assert resp["stopReason"] == "end_turn"
    assert resp["output"]["message"]["content"][0]["text"]
    assert resp["usage"]["totalTokens"] > 0
    assert resp["metrics"]["latencyMs"] >= 1


@pytest.mark.parametrize("model", [SONNET, HAIKU])
def test_boto3_converse_tool_use(live_url, model):
    resp = runtime(live_url).converse(
        modelId=model,
        system=[{"text": "Extract the customer's needs. Customer: 이서준"}],
        messages=[{"role": "user", "content": [{"text": "여행자보험이 필요해요"}]}],
        toolConfig={
            "tools": [{"toolSpec": {"name": "NeedsExtraction", "inputSchema": {"json": {"type": "object"}}}}],
            "toolChoice": {"tool": {"name": "NeedsExtraction"}},
        },
    )
    assert resp["stopReason"] == "tool_use"
    tool_use = resp["output"]["message"]["content"][0]["toolUse"]
    assert tool_use["name"] == "NeedsExtraction"
    assert NeedsExtraction.model_validate(tool_use["input"]).trip["destination_countries"] == ["JP"]


def test_boto3_converse_stream(live_url):
    resp = runtime(live_url).converse_stream(
        modelId=HAIKU,
        messages=[{"role": "user", "content": [{"text": "John Roe"}]}],
        toolConfig={"tools": [{"toolSpec": {"name": "ApplicationSummary", "inputSchema": {"json": {}}}}]},
    )
    events = list(resp["stream"])
    kinds = [next(iter(e)) for e in events]
    assert kinds == [
        "messageStart",
        "contentBlockStart",
        "contentBlockDelta",
        "contentBlockStop",
        "messageStop",
        "metadata",
    ]
    assert "John Roe" in events[2]["contentBlockDelta"]["delta"]["toolUse"]["input"]


def test_boto3_throttling_exception(live_url):
    httpx.post(f"{live_url}/_mock/faults", json={"target": "bedrock", "kind": "429", "count": 1})
    client = runtime(live_url, retries={"total_max_attempts": 1, "mode": "standard"})
    with pytest.raises(client.exceptions.ThrottlingException):
        client.converse(modelId=SONNET, messages=[{"role": "user", "content": [{"text": "hi"}]}])


def test_boto3_retries_through_throttling(live_url):
    httpx.post(f"{live_url}/_mock/faults", json={"target": "bedrock", "kind": "429", "count": 2})
    client = runtime(live_url, retries={"total_max_attempts": 3, "mode": "standard"})
    resp = client.converse(modelId=SONNET, messages=[{"role": "user", "content": [{"text": "hi"}]}])
    assert resp["stopReason"] == "end_turn"


def test_boto3_internal_server_exception(live_url):
    httpx.post(f"{live_url}/_mock/faults", json={"target": "bedrock", "kind": "500", "count": 1})
    client = runtime(live_url, retries={"total_max_attempts": 1})
    with pytest.raises(client.exceptions.InternalServerException):
        client.converse(modelId=SONNET, messages=[{"role": "user", "content": [{"text": "hi"}]}])


def test_boto3_read_timeout(live_url):
    httpx.post(
        f"{live_url}/_mock/faults",
        json={"target": "bedrock", "kind": "timeout", "count": 1, "delay_seconds": 2},
    )
    client = runtime(live_url, read_timeout=0.5, retries={"total_max_attempts": 1})
    with pytest.raises(botocore.exceptions.ReadTimeoutError):
        client.converse(modelId=SONNET, messages=[{"role": "user", "content": [{"text": "hi"}]}])


def test_langchain_structured_output_needs(live_url):
    structured = llm(live_url).with_structured_output(NeedsExtraction, method="function_calling")
    result = structured.invoke("서른다섯 살 소프트웨어 엔지니어고 서울 살아요. 고객 이름: 김하늘")
    assert isinstance(result, NeedsExtraction)
    assert result.age_range == "AGE_30_39"
    assert result.device["model"] == "Galaxy S26"


def test_langchain_model_id_with_colon(live_url):
    structured = llm(live_url, HAIKU).with_structured_output(NeedsExtraction, method="function_calling")
    result = structured.invoke("I need phone insurance. -- John Roe")
    assert result.age_range is None
    assert "age_range" in result.missing_fields


def test_langchain_all_schemas(live_url):
    model = llm(live_url)
    prompt = 'Customer: Jane Doe. [{"recommendation_id": "r-1", "product_type": "DEVICE_PROTECTION"}]'
    rationale = model.with_structured_output(RecommendationRationale, method="function_calling").invoke(
        prompt
    )
    assert rationale.items[0]["recommendation_id"] == "r-1"
    parties = model.with_structured_output(PartiesExtraction, method="function_calling").invoke(prompt)
    assert parties.all_self is True
    answers = model.with_structured_output(AnswersExtraction, method="function_calling").invoke(prompt)
    assert answers.answers["payment_method"] == "CARD"
    summary = model.with_structured_output(ApplicationSummary, method="function_calling").invoke(prompt)
    assert "Jane Doe" in summary.summary


def test_langchain_plain_and_streamed(live_url):
    model = llm(live_url)
    assert model.invoke("hello, this is 김하늘").content
    chunks = list(model.stream("hello from Jane Doe"))
    assert "".join(c.content if isinstance(c.content, str) else "" for c in chunks) or any(
        c.content for c in chunks
    )
    structured = model.with_structured_output(NeedsExtraction, method="function_calling")
    streamed = list(structured.stream("Jane Doe"))
    assert streamed and isinstance(streamed[-1], NeedsExtraction)
