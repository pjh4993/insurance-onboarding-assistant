"""LLM access. Nodes call `StructuredLLM.extract(node, schema, messages)`; production uses Bedrock
Converse through langchain-aws with the model the config bundle names for the node, tests inject a fake
with the same method."""

from __future__ import annotations

from typing import Protocol, TypeVar

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from onboarding_agent.config import Bundle, ModelProfile

T = TypeVar("T", bound=BaseModel)


class StructuredLLM(Protocol):
    async def extract(self, node: str, schema: type[T], messages: list[BaseMessage]) -> T: ...


class BedrockStructuredLLM:
    """`ChatBedrockConverse(...).with_structured_output(Schema, method="function_calling")`.

    Which model a node uses, and with which arguments, comes from the config bundle (`models` profiles,
    chosen per LLM node). Clients are cached per (profile, schema) because building one creates a boto3
    client."""

    def __init__(self, *, bundle: Bundle, region: str, endpoint_url: str | None = None) -> None:
        self._bundle = bundle
        self._region = region
        self._endpoint_url = endpoint_url
        self._cache: dict[tuple[str, str], object] = {}

    def model_for(self, node: str) -> ModelProfile:
        return self._bundle.model(node)

    def _runnable(self, node: str, schema: type[BaseModel]):
        from langchain_aws import ChatBedrockConverse

        profile = self.model_for(node)
        key = (profile.name, schema.__name__)
        if key not in self._cache:
            llm = ChatBedrockConverse(
                model=profile.model_id,
                region_name=self._region,
                endpoint_url=self._endpoint_url or None,
                **profile.args,
            )
            self._cache[key] = llm.with_structured_output(schema, method="function_calling")
        return self._cache[key]

    async def extract(self, node: str, schema: type[T], messages: list[BaseMessage]) -> T:
        result = await self._runnable(node, schema).ainvoke(messages)
        if result is None:
            raise ValueError(f"{node}: model returned no {schema.__name__} tool call")
        if isinstance(result, dict):
            result = schema.model_validate(result)
        return result
