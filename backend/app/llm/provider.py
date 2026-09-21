"""LLM access. Nodes call `StructuredLLM.extract(node, schema, messages)`; production uses Bedrock
Converse through langchain-aws, tests inject a fake with the same method."""

from __future__ import annotations

from typing import Protocol, TypeVar

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from app.config import Settings

T = TypeVar("T", bound=BaseModel)


class StructuredLLM(Protocol):
    async def extract(self, node: str, schema: type[T], messages: list[BaseMessage]) -> T: ...


class BedrockStructuredLLM:
    """`ChatBedrockConverse(...).with_structured_output(Schema, method="function_calling")`.

    The model id can be overridden per node (`LLM_MODEL_OVERRIDES`). Clients are cached per
    (model, schema) because building one creates a boto3 client."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[tuple[str, str], object] = {}

    def _runnable(self, node: str, schema: type[BaseModel]):
        from langchain_aws import ChatBedrockConverse

        model_id = self._settings.model_for(node)
        key = (model_id, schema.__name__)
        if key not in self._cache:
            llm = ChatBedrockConverse(
                model=model_id,
                region_name=self._settings.aws_region,
                endpoint_url=self._settings.bedrock_endpoint_url or None,
                temperature=0,
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
