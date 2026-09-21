"""The production LLM path — ChatBedrockConverse + with_structured_output(method="function_calling") —
against a local HTTP stand-in for the Converse API (no AWS)."""

from __future__ import annotations

import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from onboarding_agent.config import BUNDLED, load_bundle
from onboarding_agent.llm.provider import BedrockStructuredLLM
from onboarding_agent.llm.schemas import NeedsExtraction

REQUESTS: list[tuple[str, dict]] = []
BUNDLED_BASELINE = Path(str(BUNDLED)) / "1.1.0"


class ConverseHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        REQUESTS.append((self.path, body))
        tool = body["toolConfig"]["tools"][0]["toolSpec"]["name"]
        payload = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "t1",
                                "name": tool,
                                "input": {
                                    "age_range": "AGE_30_39",
                                    "residence_country": "KR",
                                    "objectives": ["PROTECT_DEVICE"],
                                    "device": {"device_category": "SMARTPHONE"},
                                    "missing_fields": [],
                                },
                            }
                        }
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
            "metrics": {"latencyMs": 1},
        }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def converse_url(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "mock")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "mock")
    server = HTTPServer(("127.0.0.1", 0), ConverseHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def bundle_with_profiles(tmp_path: Path):
    """The baseline bundle, with assess_needs moved to a second model profile."""
    bundle_dir = tmp_path / "bundle"
    shutil.copytree(BUNDLED_BASELINE, bundle_dir)
    config = json.loads((bundle_dir / "config.json").read_text())
    config["models"]["fast"] = {
        "provider": "bedrock",
        "model_id": "global.anthropic.claude-haiku-4-5",
        "args": {"temperature": 0.2, "max_tokens": 512},
    }
    (bundle_dir / "config.json").write_text(json.dumps(config))
    profiling = json.loads((bundle_dir / "flows" / "profiling.json").read_text())
    profiling["llm"]["assess_needs"]["model"] = "fast"
    (bundle_dir / "flows" / "profiling.json").write_text(json.dumps(profiling))
    return load_bundle(str(bundle_dir))


async def test_structured_output_through_converse(converse_url, tmp_path):
    REQUESTS.clear()
    llm = BedrockStructuredLLM(
        bundle=bundle_with_profiles(tmp_path), region="ap-northeast-2", endpoint_url=converse_url
    )
    out = await llm.extract(
        "assess_needs", NeedsExtraction, [SystemMessage("Customer: 김하늘"), HumanMessage("폰 보험")]
    )
    assert isinstance(out, NeedsExtraction) and out.age_range == "AGE_30_39"
    path, body = REQUESTS[0]
    # the node's model profile picks the model (in the URL) and its arguments; the tool is named after the class
    assert path.startswith("/model/global.anthropic.claude-haiku-4-5/converse")
    assert body["toolConfig"]["tools"][0]["toolSpec"]["name"] == "NeedsExtraction"
    assert body["inferenceConfig"]["temperature"] == 0.2 and body["inferenceConfig"]["maxTokens"] == 512
    assert "김하늘" in json.dumps(body, ensure_ascii=False)

    # a node on the default profile uses the default model and arguments
    await llm.extract(
        "collect_parties", NeedsExtraction, [SystemMessage("Customer: 김하늘"), HumanMessage("저 혼자요")]
    )
    path, body = REQUESTS[1]
    assert path.startswith("/model/global.anthropic.claude-sonnet-4-6/converse")
    assert body["inferenceConfig"]["temperature"] == 0 and "maxTokens" not in body["inferenceConfig"]
