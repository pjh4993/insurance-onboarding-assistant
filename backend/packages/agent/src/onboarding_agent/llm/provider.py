"""LLM access. Nodes call `StructuredLLM.extract(node, schema, messages)`; production uses Bedrock
Converse through langchain-aws, tests inject a fake with the same method."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, TypeVar

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# Nodes that call the LLM; each may be pointed at another model id (`model_overrides`).
LLM_NODES = (
    "assess_needs",
    "explain_recommendation",
    "collect_parties",
    "collect_answers",
    "summarize_application",
)


class StructuredLLM(Protocol):
    async def extract(self, node: str, schema: type[T], messages: list[BaseMessage]) -> T: ...


class BedrockStructuredLLM:
    """`ChatBedrockConverse(...).with_structured_output(Schema, method="function_calling")`.

    The model id can be overridden per node (`model_overrides`). Clients are cached per
    (model, schema) because building one creates a boto3 client."""

    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        endpoint_url: str | None = None,
        model_overrides: Mapping[str, str] | None = None,
    ) -> None:
        self._model_id = model_id
        self._region = region
        self._endpoint_url = endpoint_url
        self._overrides = dict(model_overrides or {})
        self._cache: dict[tuple[str, str], object] = {}

    def model_for(self, node: str) -> str:
        return self._overrides.get(node, self._model_id)

    def _runnable(self, node: str, schema: type[BaseModel]):
        from langchain_aws import ChatBedrockConverse

        model_id = self.model_for(node)
        key = (model_id, schema.__name__)
        if key not in self._cache:
            llm = ChatBedrockConverse(
                model=model_id,
                region_name=self._region,
                endpoint_url=self._endpoint_url or None,
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
