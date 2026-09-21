"""OpenAI access: the configured models (models.yaml) and the agent's `StructuredLLM` over OpenAI."""

from __future__ import annotations

import contextvars
import os
import time
from pathlib import Path
from typing import Any, Literal

import yaml
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from openai import AsyncOpenAI
from pydantic import BaseModel

MODELS = yaml.safe_load(Path(__file__).with_name("models.yaml").read_text())
AGENT_MODEL = os.environ.get("SIM_AGENT_MODEL", MODELS["roles"]["agent"])
CUSTOMER_MODEL = os.environ.get("SIM_CUSTOMER_MODEL", MODELS["roles"]["customer"])

# The agent LLM calls of the conversation whose turn is running; Runtime tasks copy the context they start in.
calls_var: contextvars.ContextVar[list[dict[str, Any]]] = contextvars.ContextVar("calls")


def call_kwargs(model: str, kind: Literal["tools", "parse"]) -> dict[str, Any]:
    return dict((MODELS["models"].get(model) or {}).get(kind) or {})


def openai_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    def role(m: BaseMessage) -> str:
        if isinstance(m, SystemMessage):
            return "system"
        return "assistant" if isinstance(m, AIMessage) else "user"

    return [{"role": role(m), "content": m.content if isinstance(m.content, str) else str(m.content)} for m in messages]


async def parse(client: AsyncOpenAI, schema: type[BaseModel], messages: list[dict[str, str]]) -> Any:
    """Structured output from the customer model."""
    resp = await client.chat.completions.parse(
        model=CUSTOMER_MODEL, messages=messages, response_format=schema, **call_kwargs(CUSTOMER_MODEL, "parse")
    )
    return resp.choices[0].message.parsed


class OpenAIStructuredLLM:
    """The agent's `StructuredLLM` over OpenAI function calling, the method Bedrock uses."""

    def __init__(self, client: AsyncOpenAI, model: str = AGENT_MODEL) -> None:
        self._client = client
        self._model = model

    async def extract(self, node: str, schema: type[BaseModel], messages: list[BaseMessage]) -> Any:
        name = schema.__name__
        tool = {
            "type": "function",
            "function": {"name": name, "description": schema.__doc__ or name, "parameters": schema.model_json_schema()},
        }
        started = time.monotonic()
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=openai_messages(messages),
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": name}},
            **call_kwargs(self._model, "tools"),
        )
        tool_calls = resp.choices[0].message.tool_calls
        if not tool_calls:
            raise ValueError(f"{node}: model returned no {name} tool call")
        result = schema.model_validate_json(tool_calls[0].function.arguments)
        calls_var.get([]).append(
            {
                "node": node,
                "schema": name,
                "model": self._model,
                "input": openai_messages(messages),
                "output": result.model_dump(),
                "latency_s": round(time.monotonic() - started, 2),
                "usage": resp.usage.model_dump() if resp.usage else None,
            }
        )
        return result
