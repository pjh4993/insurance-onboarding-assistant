"""Runtime settings, read from the environment (CONTRACTS.md §2)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Nodes that call the LLM. `LLM_MODEL_OVERRIDES` may point any of them at another model id.
LLM_NODES = (
    "assess_needs",
    "explain_recommendation",
    "collect_parties",
    "collect_answers",
    "summarize_application",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = "postgresql+psycopg://onboarding:onboarding@localhost:15432/onboarding"

    partner_api_url: str = "http://localhost:18080/partner"
    identity_api_url: str = "http://localhost:18080/identity"
    contract_api_url: str = "http://localhost:18080/contract"
    http_timeout_seconds: float = 10.0

    bedrock_endpoint_url: str | None = None
    bedrock_model_id: str = "global.anthropic.claude-sonnet-4-6"
    aws_region: str = "ap-northeast-2"
    # JSON object {node_name: model_id}; e.g. {"assess_needs": "global.anthropic.claude-haiku-4-5"}
    llm_model_overrides: dict[str, str] = Field(default_factory=dict)

    checkpoint_aes_key: str = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
    session_hmac_key: str = "dev-session-hmac-key"
    session_link_ttl_hours: int = 48

    retry_max_attempts: int = 3
    retry_initial_interval: float = 0.5

    sse_ping_seconds: float = 15.0
    # memory: one process only. postgres: LISTEN/NOTIFY, needed once the backend runs more than one task.
    sse_broker: Literal["memory", "postgres"] = "memory"

    log_level: str = "INFO"
    # Cap on one log line (message, and separately its traceback tail) and on any span attribute value.
    log_max_chars: int = 2000

    @field_validator("bedrock_endpoint_url", mode="before")
    @classmethod
    def _empty_to_none(cls, v: object) -> object:
        return v or None

    @field_validator("checkpoint_aes_key")
    @classmethod
    def _check_key(cls, v: str) -> str:
        if len(bytes.fromhex(v)) not in (16, 24, 32):
            raise ValueError("CHECKPOINT_AES_KEY must be 32, 48 or 64 hex characters")
        return v

    @property
    def aes_key_bytes(self) -> bytes:
        return bytes.fromhex(self.checkpoint_aes_key)

    @property
    def psycopg_conninfo(self) -> str:
        """The DATABASE_URL without the SQLAlchemy driver suffix, for raw psycopg."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    def model_for(self, node: str) -> str:
        return self.llm_model_overrides.get(node, self.bedrock_model_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
