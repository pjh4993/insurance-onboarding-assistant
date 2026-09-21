"""Runtime settings, read from the environment (CONTRACTS.md §2)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = "postgresql+psycopg://onboarding:onboarding@localhost:15432/onboarding"

    partner_api_url: str = "http://localhost:18080/partner"
    identity_api_url: str = "http://localhost:18080/identity"
    contract_api_url: str = "http://localhost:18080/contract"
    http_timeout_seconds: float = 10.0

    bedrock_endpoint_url: str | None = None
    aws_region: str = "ap-northeast-2"

    # The agent config bundle (models, prompts, copy): a local directory or s3://bucket/prefix holding one
    # directory per version. Unset: the baseline bundle shipped with the agent package.
    agent_config_uri: str | None = None
    # Exact (1.2.0) or a prefix (1, 1.2) meaning the highest published version under it. Unset: the newest
    # version the agent supports.
    agent_config_version: str | None = None
    # Comma-separated model ids the bundle may name (what the IAM policy allows). Unset: not checked.
    llm_allowed_model_ids: str | None = None

    checkpoint_aes_key: str = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
    session_hmac_key: str = "dev-session-hmac-key"
    session_link_ttl_hours: int = 48
    # Public self-serve starts (POST /api/public/sessions), counted from the DB over the last hour.
    self_serve_per_ip_per_hour: int = 5
    self_serve_per_hour: int = 200

    retry_max_attempts: int = 3
    retry_initial_interval: float = 0.5

    sse_ping_seconds: float = 15.0
    # memory: one process only. postgres: LISTEN/NOTIFY, needed once the backend runs more than one task.
    sse_broker: Literal["memory", "postgres"] = "memory"

    log_level: str = "INFO"
    # Cap on one log line (message, and separately its traceback tail) and on any span attribute value.
    log_max_chars: int = 2000

    @field_validator("bedrock_endpoint_url", "agent_config_uri", "agent_config_version", mode="before")
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
    def allowed_model_ids(self) -> list[str] | None:
        if not self.llm_allowed_model_ids:
            return None
        return [m.strip() for m in self.llm_allowed_model_ids.split(",") if m.strip()]

    @property
    def aes_key_bytes(self) -> bytes:
        return bytes.fromhex(self.checkpoint_aes_key)

    @property
    def psycopg_conninfo(self) -> str:
        """The DATABASE_URL without the SQLAlchemy driver suffix, for raw psycopg."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
